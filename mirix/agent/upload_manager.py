import os
import time
import uuid
import queue
import threading
from PIL import Image
from concurrent.futures import ThreadPoolExecutor, TimeoutError as FutureTimeoutError


class UploadManager:
    """
    Handles background uploading of files to cloud storage.
    Provides async upload capabilities with proper cleanup.
    """
    
    def __init__(self, google_client, client, existing_files, uri_to_create_time):
        self.google_client = google_client
        self.client = client
        self.existing_files = existing_files
        self.uri_to_create_time = uri_to_create_time
        
        # Initialize upload queue and workers for background image uploading
        self._upload_queue = queue.Queue()
        self._upload_results = {}  # uuid -> file_ref or exception
        self._upload_results_lock = threading.Lock()
        self._upload_workers_running = True
        self._cleanup_threshold = 100  # Clean up after this many resolved uploads accumulate
        
        # Start background upload workers
        self._upload_workers = []
        for i in range(4):  # Use 2 worker threads for parallel uploads
            worker = threading.Thread(target=self._upload_worker, daemon=True)
            worker.start()
            self._upload_workers.append(worker)
    
    def _compress_image(self, image_path, quality=85, max_size=(1920, 1080)):
        """Compress image to reduce upload time while maintaining reasonable quality"""
        try:
            with Image.open(image_path) as img:
                # Convert to RGB if necessary
                if img.mode in ('RGBA', 'LA', 'P'):
                    img = img.convert('RGB')
                
                # Resize if too large
                img.thumbnail(max_size, Image.Resampling.LANCZOS)
                
                # Create compressed version with proper extension handling
                base_path = os.path.splitext(image_path)[0]
                compressed_path = f"{base_path}_compressed.jpg"
                img.save(compressed_path, 'JPEG', quality=quality, optimize=True)
                
                # Verify the compressed file was actually created
                if os.path.exists(compressed_path):
                    return compressed_path
                else:
                    return None
                
                # # Get file sizes for comparison
                # original_size = os.path.getsize(image_path)
                # compressed_size = os.path.getsize(compressed_path)
                
        except Exception as e:
            print(f"Image compression failed for {image_path}: {e}")
            return None
    
    def _upload_worker(self):
        """Background worker that processes the upload queue"""
        while self._upload_workers_running:
            try:
                # Get upload task from queue (blocking with timeout)
                upload_task = self._upload_queue.get(timeout=1.0)
                if upload_task is None:  # Shutdown signal
                    break
                    
                upload_uuid, filename, timestamp, compressed = upload_task
                
                try:
                    # Perform the actual upload
                    if self.client.server.cloud_file_mapping_manager.check_if_existing(local_file_id=filename):
                        cloud_file_name = self.client.server.cloud_file_mapping_manager.get_cloud_file(local_file_id=filename)
                        file_ref = [x for x in self.existing_files if x.name == cloud_file_name][0]
                    else:
                        # Use compressed file if available and exists, otherwise use original
                        upload_file = filename  # Default to original file
                        if compressed and os.path.exists(compressed):
                            upload_file = compressed
                        elif compressed and not os.path.exists(compressed):
                            print(f"Warning: Compressed file {compressed} does not exist, using original file {filename}")
                        
                        t1 = time.time()
                        
                        # Retry upload up to 3 times with 1 second delay between attempts
                        max_retries = 3
                        retry_delay = 1.0
                        upload_timeout = 30.0  # 30 second timeout per upload attempt
                        upload_successful = False
                        
                        for attempt in range(max_retries):
                            try:
                                # Use ThreadPoolExecutor to implement timeout for upload
                                with ThreadPoolExecutor(max_workers=1) as executor:
                                    upload_start_time = time.time()
                                    future = executor.submit(self.google_client.files.upload, file=upload_file)
                                    
                                    try:
                                        file_ref = future.result(timeout=upload_timeout)
                                        upload_end_time = time.time()
                                        upload_duration = upload_end_time - upload_start_time
                                        print(f"Upload completed in {upload_duration:.2f} seconds for file {upload_file}")
                                        upload_successful = True
                                        break
                                    except FutureTimeoutError:
                                        # Cancel the future to clean up resources
                                        future.cancel()
                                        upload_duration = time.time() - upload_start_time
                                        raise Exception(f"Upload timed out after {upload_duration:.2f} seconds (limit: {upload_timeout}s)")
                                        
                            except Exception as e:
                                error_msg = f"Upload attempt {attempt + 1} failed for file {upload_file}: {e}"
                                print(error_msg)
                                
                                if attempt < max_retries - 1:  # Not the last attempt
                                    print(f"Retrying in {retry_delay} seconds...")
                                    time.sleep(retry_delay)
                                else:  # Last attempt failed
                                    # If we were trying to upload compressed file, try original as fallback
                                    if upload_file != filename:
                                        print(f"All attempts failed for compressed file, trying original file {filename}")
                                        for fallback_attempt in range(max_retries):
                                            try:
                                                # Apply timeout to fallback attempts as well
                                                with ThreadPoolExecutor(max_workers=1) as executor:
                                                    fallback_start_time = time.time()
                                                    future = executor.submit(self.google_client.files.upload, file=filename)
                                                    
                                                    try:
                                                        file_ref = future.result(timeout=upload_timeout)
                                                        fallback_end_time = time.time()
                                                        fallback_duration = fallback_end_time - fallback_start_time
                                                        print(f"Fallback upload completed in {fallback_duration:.2f} seconds for file {filename}")
                                                        upload_successful = True
                                                        # Update upload_file for cleanup logic
                                                        upload_file = filename
                                                        break
                                                    except FutureTimeoutError:
                                                        # Cancel the future to clean up resources
                                                        future.cancel()
                                                        fallback_duration = time.time() - fallback_start_time
                                                        raise Exception(f"Fallback upload timed out after {fallback_duration:.2f} seconds (limit: {upload_timeout}s)")
                                                        
                                            except Exception as fallback_e:
                                                print(f"Fallback attempt {fallback_attempt + 1} failed for file {filename}: {fallback_e}")
                                                if fallback_attempt < max_retries - 1:
                                                    print(f"Retrying fallback in {retry_delay} seconds...")
                                                    time.sleep(retry_delay)
                                    
                                    if not upload_successful:
                                        raise Exception(f"Failed to upload file after {max_retries} attempts for both compressed and original files")
                        
                        if not upload_successful:
                            raise Exception(f"Upload failed after {max_retries} attempts")
                            
                        t2 = time.time()
                        
                        print(f"Uploaded file {file_ref.name} in {t2 - t1} seconds")

                        self.uri_to_create_time[file_ref.uri] = {'create_time': file_ref.create_time, 'filename': file_ref.name}
                        self.client.server.cloud_file_mapping_manager.add_mapping(
                            local_file_id=filename, 
                            cloud_file_id=file_ref.uri, 
                            timestamp=timestamp, 
                            force_add=True
                        )
                        
                        # Clean up compressed file if it was created and used
                        if compressed and compressed != filename and upload_file == compressed and os.path.exists(compressed):
                            os.remove(compressed)
                    
                    # Store successful result
                    with self._upload_results_lock:
                        self._upload_results[upload_uuid] = file_ref
                        
                except Exception as e:
                    # Store exception for later handling
                    with self._upload_results_lock:
                        self._upload_results[upload_uuid] = e
                
                finally:
                    self._upload_queue.task_done()
                    # Periodically clean up old results
                    self._maybe_cleanup_old_results()
                    
            except queue.Empty:
                continue  # Timeout, check shutdown flag and continue
            except Exception as e:
                pass
    
    def upload_file_async(self, filename, timestamp, compress=True):
        """Queue an image for background upload and return immediately with a placeholder"""
        upload_uuid = str(uuid.uuid4())
        
        # Optionally compress the image first
        compressed_file = None
        if compress and filename.lower().endswith(('.png', '.jpg', '.jpeg')):
            compressed_file = self._compress_image(filename)
        
        # Queue the upload task
        self._upload_queue.put((upload_uuid, filename, timestamp, compressed_file))
        
        # Return a placeholder that can be resolved later
        return {'upload_uuid': upload_uuid, 'filename': filename, 'pending': True}
    
    def wait_for_upload(self, placeholder, timeout=30):
        """Wait for a background upload to complete and return the file reference"""
        if not isinstance(placeholder, dict) or not placeholder.get('pending'):
            return placeholder  # Already resolved
            
        upload_uuid = placeholder['upload_uuid']
        start_time = time.time()
        
        while time.time() - start_time < timeout:
            with self._upload_results_lock:
                if upload_uuid in self._upload_results:
                    result = self._upload_results.get(upload_uuid)  # Use get() instead of pop()
                    if isinstance(result, Exception):
                        # Remove failed upload from results to avoid memory leaks
                        self._upload_results.pop(upload_uuid, None)
                        raise result
                    return result
            time.sleep(0.1)
        
        raise TimeoutError(f"Upload timeout after {timeout}s for {placeholder['filename']}")
    
    def try_resolve_upload(self, placeholder):
        """Try to resolve an upload without blocking. Returns None if still pending."""
        if not isinstance(placeholder, dict) or not placeholder.get('pending'):
            return placeholder  # Already resolved
            
        upload_uuid = placeholder['upload_uuid']
        with self._upload_results_lock:
            if upload_uuid in self._upload_results:
                result = self._upload_results.get(upload_uuid)  # Use get() instead of pop()
                if isinstance(result, Exception):
                    # Remove failed upload from results to avoid memory leaks
                    self._upload_results.pop(upload_uuid, None)
                    return None
                return result
        return None  # Still pending
    
    def upload_file(self, filename, timestamp):
        """Legacy synchronous upload method - now uses async under the hood"""
        placeholder = self.upload_file_async(filename, timestamp)
        return self.wait_for_upload(placeholder, timeout=90)
    
    def cleanup_resolved_upload(self, placeholder):
        """Remove a resolved upload result from memory to prevent memory leaks."""
        if not isinstance(placeholder, dict) or not placeholder.get('pending'):
            return  # Not a pending placeholder
            
        upload_uuid = placeholder['upload_uuid']
        with self._upload_results_lock:
            self._upload_results.pop(upload_uuid, None)
    
    def _maybe_cleanup_old_results(self):
        """Clean up old upload results if we've accumulated too many."""
        with self._upload_results_lock:
            if len(self._upload_results) > self._cleanup_threshold:
                # Keep only the most recent results (this is a simple cleanup strategy)
                # In a more sophisticated implementation, we could track timestamps
                # For now, just clear all since they should have been processed by now
                # A more sophisticated approach would track access times
                self._upload_results.clear()
    
    def cleanup_upload_workers(self):
        """Gracefully shut down upload workers"""
        self._upload_workers_running = False
        
        # Send shutdown signals to all workers
        for _ in self._upload_workers:
            self._upload_queue.put(None)
        
        # Wait for workers to finish
        for worker in self._upload_workers:
            worker.join(timeout=5.0) 