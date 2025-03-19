# Yes, This Was Always a Promp(t) 🧙‍♂️
<p align="center">
  <img src="/assets/gemini_intro.jpg" alt="Gemini" width="600"/>
</p>

An AI-powered watermark removal tool that uses Google's Gemini to magically erase watermarks from images. It's amazing how AI is changing the way we create and code. Tools like Gemini make it possible to build things faster, solve real problems, and explore new ideas with ease. This tool is just one small example of what's possible!

However, this is not about promoting piracy. The use of this tool should be done responsibly, respecting copyright laws and only for ethical purposes, such as removing watermarks from your own images or those you have permission to edit. 🚀

## 🌟 Features

- **AI-Powered Removal**: Leverages Google Gemini to intelligently identify and remove watermarks
- **User-Friendly Interface**: Simple drag-and-drop or click-to-upload functionality
- **Real-time Preview**: Side-by-side comparison of original and processed images
- **Privacy Focused**: Files are automatically deleted after 10 minutes

## 🚀 Getting Started

### Prerequisites

- Python 3.9+
- Google Gemini API Key
- Flask and other dependencies

### Installation

1. Clone the repository:
   ```bash
   git clone https://github.com/yourusername/removewatermarkfromimage.git
   cd removewatermarkfromimage
   ```

2. Create a virtual environment:
   ```bash
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

4. Create a `.env` file in the root directory with your API keys:
   ```
   GEMINI_API_KEY=your_gemini_api_key_here
   ```

### Setting up Google OAuth

This application uses Google OAuth for user authentication. Follow these steps to set it up:

1. Go to the [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select an existing one
3. Navigate to "APIs & Services" > "Credentials"
4. Click "Create Credentials" and select "OAuth client ID"
5. Select "Web application" as the application type
6. Give your OAuth client a name
7. Add authorized redirect URIs:
   - For local development: `http://localhost:5000/callback`
   - For production: `https://yourdomain.com/callback`
8. Click "Create"
9. Copy your Client ID and Client Secret
10. Add them to your `.env` file:
    ```
    GEMINI_API_KEY=your_gemini_api_key_here
    GOOGLE_CLIENT_ID=your_google_client_id_here
    GOOGLE_CLIENT_SECRET=your_google_client_secret_here
    SECRET_KEY=a_random_secret_key_for_flask
    ```

### Running Locally

Start the Flask development server:
```bash
python main.py
```

Visit `http://127.0.0.1:5000` in your browser.

## 🔍 How It Works

1. User uploads an image containing a watermark
2. The application sends the image to Google's Gemini model
3. A prompt instructs the AI to identify and remove the watermark while preserving the rest of the image
4. The processed image is returned and displayed alongside the original

## 🛠️ Technologies Used

- **Backend**: Flask (Python)
- **AI**: Google Gemini
- **Frontend**: HTML, CSS, JavaScript (Vanilla)
- **Deployment**: Vercel

## 📝 Legal Notice

This tool is provided for educational and legitimate personal use only. Users must agree to only use this service on images they have the legal right to modify. Removing watermarks from copyrighted material without permission may violate copyright laws. Users assume all liability for how they use this tool and the processed images.

## 📄 License

This project is licensed under the MIT License - see the LICENSE file for details.

## 👏 Acknowledgments

- Google Gemini API for providing the AI capabilities
- The open source community for inspiration and tools
