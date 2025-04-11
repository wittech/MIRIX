![Mirix Logo](assets/logo.png)

## Overview

**Mirix** is a multi-agent personal assistant designed to track on-screen activities and answer user questions intelligently. By capturing real-time visual data and consolidating it into structured memories, Mirix transforms raw inputs into a rich knowledge base that adapts to your digital experiences.

Mirix leverages a unique multi-layered memory system comprising six distinct memory components and eight specialized agents, ensuring that data is processed efficiently and securely.

<!-- ![Examples](assets/mirix_exp.jpg) -->

## Features

### Multi-Agent System

Mirix consists of eight specialized agents that work collaboratively:

- **Meta Agent:** Coordinates and updates various memory agents.
- **Chat Agent:** Engages in natural language conversations with the user.
- **Memory Managers:** Six agents each dedicated to managing one of the memory components:
  - **Core Memory:** Stores essential and persistent user data.
  - **Episodic Memory:** Captures context-specific events and interactions.
  - **Semantic Memory:** Maintains general knowledge, concepts, and abstracted information.
  - **Resource Memory:** Manages active documents and project-related files.
  - **Knowledge Vault:** Securely stores structured personal data (e.g., contacts, credentials).
  - **Procedural Memory:** Records process workflows and step-by-step instructions.

### Intelligent Memory Consolidation

Mirix does not simply store raw data. Instead, it processes screen captures and contextual inputs to generate organized, searchable knowledge. This ensures that your digital experiences are converted into meaningful insights without overwhelming the system with unstructured information.

### Security & Privacy

- **Screenshot Handling:**  
  - Takes a screenshot every second and uploads the most recent 600 (roughly 10 minutes of data) to your personal Google Cloud storage.
  - Automatically deletes older screenshots to enhance privacy.
- **Local Data Storage:**  
  - Consolidated information is stored locally in a secure SQLite database located at `~/.mirix/sqlite.db`.
- **User-Controlled Privacy:**  
  - All long-term user data remains local, and only your own Google Cloud account is used for temporary storage of screenshots.
  - Designed with security practices akin to how modern browsers safely store sensitive data.

## Installation

### Prerequisites

- Python 3.11 or later
- A valid [GEMINI API key](https://your-api-key-provider.com)

### Setup

1. **Clone the Repository:**
    ```bash
    git clone https://github.com/Mirix-AI/Mirix.git
    cd Mirix
    ```

2. **Configure the Environment:**
    Create a file named `.env` in the project root and add your GEMINI API key:
    ```dotenv
    GEMINI_API_KEY=your_api_key_here
    ```

3. **Install Dependencies:**
    ```bash
    pip install -r requirements.txt
    ```

4. **Start Mirix:**
    ```bash
    python main.py
    ```

Mirix will initialize its multi-agent system and begin processing on-screen activities immediately.

## Evaluation Results

**Dataset 1 (1.5 hours, 700 images):**  
For evaluation, approximately 700 images were collected capturing one user's (the author’s) activities between 0:00 and 1:30 AM on March 9th. Questions were then posed regarding these activities, resulting in the following performance outcomes:

| Model                  | Accuracy            |
|------------------------|---------------------|
| Gemini                 | 0.0833 (1/12)       |
| Letta                  | Not Applicable      |
| Letta-MultiModal       | Under Development   |
| Mem0                   | Not Applicable      |
| **Mirix-2025-04-08**   | **0.4167 (5/12)**   |

## License

Mirix is released under the MIT License. See the [LICENSE](LICENSE) file for more details.

## Contact

For questions, suggestions, or issues, please open an issue on the GitHub repository or contact us at `yuw164@ucsd.edu`

## Acknowledgement
We would like to thank [Letta](https://github.com/letta-ai/letta)  for open-sourcing their framework, which served as the foundation for the memory system in this project.
