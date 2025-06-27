import os
import random
import json
import argparse
import base64
from typing import List, Dict
from dotenv import load_dotenv
from tqdm import tqdm
from google import genai
from datetime import datetime

# -----------------------------------------------------------------------------
# Configuration constants
# -----------------------------------------------------------------------------
QUESTIONS_PER_BATCH = 5  # Number of questions to generate in each API call

# -----------------------------------------------------------------------------
# Utility helpers
# -----------------------------------------------------------------------------

def encode_image_to_base64(image_path: str) -> str:
    """Return base64 encoded string for the given image."""
    with open(image_path, "rb") as img_file:
        return base64.b64encode(img_file.read()).decode("utf-8")


def gather_images(dataset_root: str, student: str) -> List[str]:
    """Return a sorted list of image paths for the given student folder."""
    student_dir = os.path.join(dataset_root, student)
    if not os.path.isdir(student_dir):
        raise FileNotFoundError(f"Student directory not found: {student_dir}")

    # Only include typical image extensions
    exts = {".png", ".jpg", ".jpeg"}
    imgs = [
        os.path.join(student_dir, f)
        for f in os.listdir(student_dir)
        if os.path.splitext(f)[1].lower() in exts
    ]
    imgs.sort()  # ensure chronological order
    return imgs


def choose_consecutive_slice(items: List[str], count: int) -> List[str]:
    """Randomly choose `count` consecutive items from `items`."""
    if count > len(items):
        raise ValueError("Requested slice length exceeds available items")
    start = random.randint(0, len(items) - count)
    return items[start : start + count]


def extract_timestamp_from_filename(image_path: str) -> str:
    """Extract timestamp from image filename and format it as a readable date."""
    filename = os.path.basename(image_path)
    # Assuming filename format like "20250516_235610.png"
    if len(filename) >= 15 and filename[:8].isdigit() and filename[9:15].isdigit():
        date_part = filename[:8]  # YYYYMMDD
        time_part = filename[9:15]  # HHMMSS
        
        try:
            # Parse the date and time
            year = int(date_part[:4])
            month = int(date_part[4:6])
            day = int(date_part[6:8])
            hour = int(time_part[:2])
            minute = int(time_part[2:4])
            second = int(time_part[4:6])
            
            dt = datetime(year, month, day, hour, minute, second)
            return dt.strftime("%B %d, %Y")  # e.g., "May 16, 2025"
        except ValueError:
            pass
    
    return "that day"


def build_prompt(num_images: int, num_questions: int, session_date: str) -> str:
    """Return the textual instruction for Gemini."""
    return (
        f"You will be shown {num_images} consecutive screenshots from {session_date} that form a sequence from my computer session. "
        f"Generate exactly {num_questions} question-answer pairs from MY PERSPECTIVE (first-person) that require understanding the ENTIRE sequence of screenshots. "
        f"The questions should be phrased as if I am asking about what I did on {session_date}.\n\n"
        "Your questions should synthesize information across multiple images and focus on:\n"
        "1. Workflows or tasks that I completed across multiple screenshots\n"
        "2. Websites, repositories, or resources that I visited during that session\n"
        "3. Files I worked with, directories I navigated, or projects I worked on\n"
        "4. Research topics I explored or information I gathered\n"
        "5. Applications I used and activities I performed\n"
        "6. Any patterns in my behavior or work during that session\n\n"
        "IMPORTANT: \n"
        "- Questions should be from MY perspective (use 'I', 'my', 'me')\n"
        f"- Reference the specific date ({session_date}) when relevant\n"
        "- Questions should NOT be answerable from just one screenshot\n"
        "- Assume the person answering has access to a much broader set of screenshots from around that time period\n\n"
        "Examples of good first-person questions:\n"
        f"- \"What GitHub repositories did I visit on {session_date} and what were they about?\"\n"
        f"- \"What was the complete workflow I followed on {session_date} to set up my development environment?\"\n"
        f"- \"What files did I create or modify during my coding session on {session_date}?\"\n"
        f"- \"What research topics did I explore on {session_date} and what resources did I find?\"\n"
        f"- \"What applications did I use on {session_date} and what activities did I perform in each?\"\n"
        f"- \"On {session_date}, what was the sequence of steps I followed to debug that issue?\"\n\n"
        "Return your result as valid JSON with the following schema:\n"
        "{\n"
        "  \"qas\": [\n"
        "    {\n"
        "      \"question\": <string>, // First-person question about activities on the specific date\n"
        "      \"answer\": <string>,   // Comprehensive answer synthesizing information from the sequence\n"
        "    },\n"
        "    ...\n"
        "  ]\n"
        "}\n"
    )


def prepare_multimodal_parts(image_paths: List[str], num_questions: int) -> List[Dict]:
    """Prepare the multimodal message parts for Gemini."""
    # Extract timestamp from the first image
    session_date = extract_timestamp_from_filename(image_paths[0])
    
    contents = {'role': 'user', 'parts': []}
    
    # Add all images with their markers
    for idx, img_path in enumerate(image_paths):
        base64_data = encode_image_to_base64(img_path)
        mime_type = "image/png" if img_path.lower().endswith(".png") else "image/jpeg"
        contents['parts'].extend([
            {"text": f"\nImage {idx}:\n"},
            {
                "inline_data": {
                    "mime_type": mime_type,
                    "data": base64_data
                }
            }])

    # Add the instruction prompt at the end
    contents['parts'].append({"text": "\n" + build_prompt(len(image_paths), num_questions, session_date)})
    
    return contents


def call_gemini_batch(client, image_paths: List[str], num_questions: int) -> Dict:
    """Send all images to Gemini in one batch and return parsed QA dict."""
    contents = prepare_multimodal_parts(image_paths, num_questions)
    
    response = client.models.generate_content(
        model="gemini-2.0-flash-exp",
        contents=contents
    )
    
    text = response.text.strip()

    # Try to parse JSON safely
    try:
        # Gemini sometimes wraps JSON in markdown fences; strip them
        if text.startswith("```json"):
            text = text.strip("```json").strip("```")
        data = json.loads(text)
    except Exception as e:
        print(f"Failed to parse JSON response: {e}")
        data = {"raw": text}

    return data


def generate_qa_batches(client, all_images: List[str], total_questions: int, images_per_batch: int) -> List[Dict]:
    """Generate QA pairs by selecting different image sets for each batch."""
    num_batches = total_questions // QUESTIONS_PER_BATCH
    remaining_questions = total_questions % QUESTIONS_PER_BATCH
    
    all_qa_pairs = []
    all_selected_images = []  # Keep track of all image sets used
    
    print(f"Generating {total_questions} questions in {num_batches} batches of {QUESTIONS_PER_BATCH} questions each...")
    if remaining_questions > 0:
        print(f"Plus 1 additional batch with {remaining_questions} questions.")
    
    total_batches = num_batches + (1 if remaining_questions > 0 else 0)
    
    # Generate full batches
    for batch_num in tqdm(range(num_batches), desc="Generating QA batches"):
        print(f"\nBatch {batch_num + 1}/{total_batches}: Selecting {images_per_batch} consecutive images and generating {QUESTIONS_PER_BATCH} questions...")
        
        try:
            # Select a new set of consecutive images for this batch
            selected_images = choose_consecutive_slice(all_images, images_per_batch)
            start_index = all_images.index(selected_images[0])
            print(f"Selected images from index {start_index} to {start_index + images_per_batch - 1}")
            
            qa_data = call_gemini_batch(client, selected_images, QUESTIONS_PER_BATCH)
            if "qas" in qa_data and isinstance(qa_data["qas"], list):
                # Add batch info to each QA pair
                for qa in qa_data["qas"]:
                    qa["batch_info"] = {
                        "batch_number": batch_num + 1,
                        "images_start_index": start_index,
                        "images_end_index": start_index + images_per_batch - 1,
                        "session_date": extract_timestamp_from_filename(selected_images[0])
                    }
                all_qa_pairs.extend(qa_data["qas"])
                all_selected_images.append({
                    "batch_number": batch_num + 1,
                    "images": selected_images,
                    "start_index": start_index
                })
                print(f"Successfully generated {len(qa_data['qas'])} questions in batch {batch_num + 1}")
            else:
                print(f"Warning: Batch {batch_num + 1} returned unexpected format: {qa_data}")
        except Exception as e:
            print(f"Error in batch {batch_num + 1}: {e}")
    
    # Generate remaining questions if any
    if remaining_questions > 0:
        batch_num = num_batches
        print(f"\nFinal batch {batch_num + 1}/{total_batches}: Selecting {images_per_batch} consecutive images and generating {remaining_questions} questions...")
        try:
            # Select a new set of consecutive images for the final batch
            selected_images = choose_consecutive_slice(all_images, images_per_batch)
            start_index = all_images.index(selected_images[0])
            print(f"Selected images from index {start_index} to {start_index + images_per_batch - 1}")
            
            qa_data = call_gemini_batch(client, selected_images, remaining_questions)
            if "qas" in qa_data and isinstance(qa_data["qas"], list):
                # Add batch info to each QA pair
                for qa in qa_data["qas"]:
                    qa["batch_info"] = {
                        "batch_number": batch_num + 1,
                        "images_start_index": start_index,
                        "images_end_index": start_index + images_per_batch - 1,
                        "session_date": extract_timestamp_from_filename(selected_images[0])
                    }
                all_qa_pairs.extend(qa_data["qas"])
                all_selected_images.append({
                    "batch_number": batch_num + 1,
                    "images": selected_images,
                    "start_index": start_index
                })
                print(f"Successfully generated {len(qa_data['qas'])} questions in final batch")
            else:
                print(f"Warning: Final batch returned unexpected format: {qa_data}")
        except Exception as e:
            print(f"Error in final batch: {e}")
    
    return all_qa_pairs, all_selected_images


# -----------------------------------------------------------------------------
# Main script
# -----------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Generate QA pairs for ScreenshotVQA using Gemini")
    parser.add_argument("--dataset_root", default="data/ScreenshotVQA", help="Root directory of ScreenshotVQA dataset")
    parser.add_argument("--student", choices=["student1", "student2", "student3"], default="student2", help="Which student folder to sample from")
    parser.add_argument("--count", type=int, default=100, help="Number of consecutive images to sample per batch")
    parser.add_argument("--num_questions", type=int, default=50, help="Total number of QA pairs to generate")
    parser.add_argument("--output", default="qa_results.json", help="Path to write output JSON")
    parser.add_argument("--seed", type=int, default=None, help="Random seed for reproducibility")
    args = parser.parse_args()

    # Random seed
    if args.seed is not None:
        random.seed(args.seed)

    print(f"Configuration: Generating {args.num_questions} questions in batches of {QUESTIONS_PER_BATCH}")
    print(f"Each batch will use {args.count} consecutive images")

    # ------------------------------------------------------------------
    # Configure Gemini client
    # ------------------------------------------------------------------
    load_dotenv()
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise EnvironmentError("Please set GEMINI_API_KEY in your environment")

    client = genai.Client(api_key=api_key)

    # ------------------------------------------------------------------
    # Gather all images from the student folder
    # ------------------------------------------------------------------
    all_images = gather_images(args.dataset_root, args.student)
    print(f"Found {len(all_images)} total images in {args.student}")

    # ------------------------------------------------------------------
    # Generate QAs in batches with different image sets
    # ------------------------------------------------------------------
    all_qa_pairs, all_selected_images = generate_qa_batches(client, all_images, args.num_questions, args.count)
    
    # Prepare final results
    results = {
        "total_questions_generated": len(all_qa_pairs),
        "questions_per_batch": QUESTIONS_PER_BATCH,
        "images_per_batch": args.count,
        "total_batches": len(all_selected_images),
        "student": args.student,
        "qa_pairs": all_qa_pairs,
        "image_batches": all_selected_images  # Keep track of which images were used for each batch
    }

    # ------------------------------------------------------------------
    # Persist results
    # ------------------------------------------------------------------
    with open(args.output, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\nSaved {len(all_qa_pairs)} QA pairs from {len(all_selected_images)} different image batches to {args.output}")


if __name__ == "__main__":
    main()
