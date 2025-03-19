import os
from flask import Flask, render_template, request, send_file, redirect, url_for, session
from google import genai
from google.genai import types
import uuid
import logging
import threading
import time
import base64
import os
from dateutil import parser 
from flask_login import LoginManager, UserMixin, login_user, logout_user, login_required, current_user
from authlib.integrations.flask_client import OAuth
from urllib.parse import urlencode
import requests

def encode_image_to_base64(file_path, mime_type="image/png"):
    with open(file_path, "rb") as image_file:
        encoded_string = base64.b64encode(image_file.read()).decode("utf-8")
    return f"data:{mime_type};base64,{encoded_string}"


app = Flask(__name__, static_folder='static')
app.config['UPLOAD_FOLDER'] = '/tmp/uploads'
app.config['GENERATED_FOLDER'] = '/tmp/generated'
app.config['FILE_TTL'] = 600  # Time to live for files in seconds (10 minutes)
# Add secret key for session security
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', os.urandom(24).hex())

# Set preferred URL scheme for external URLs
if os.environ.get('FLASK_ENV') == 'production' or os.environ.get('PRODUCTION') == 'true':
    app.config['PREFERRED_URL_SCHEME'] = 'https'
else:
    app.config['PREFERRED_URL_SCHEME'] = 'http'

# Configure Google OAuth
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.environ.get("GOOGLE_CLIENT_ID"),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET"),
    access_token_url='https://accounts.google.com/o/oauth2/token',
    access_token_params=None,
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    authorize_params={
        'prompt': 'consent',
        'access_type': 'offline'
    },
    api_base_url='https://www.googleapis.com/oauth2/v1/',
    userinfo_endpoint='https://openidconnect.googleapis.com/v1/userinfo',
    client_kwargs={
        'scope': 'openid email profile',
        'prompt': 'consent',
    },
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration'
)

login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'
login_manager.login_message = "Please sign in to access this page."
login_manager.login_message_category = "info"

@login_manager.unauthorized_handler
def unauthorized():
    # Redirect to login page
    return redirect(url_for('login'))

# User model for Flask-Login
class User(UserMixin):
    def __init__(self, id, name, email, profile_pic):
        self.id = id
        self.name = name
        self.email = email
        self.profile_pic = profile_pic

@login_manager.user_loader
def load_user(user_id):
    if 'user_info' in session:
        user_info = session['user_info']
        return User(
            id=user_info.get('id'),
            name=user_info.get('name'),
            email=user_info.get('email'),
            profile_pic=user_info.get('picture')
        )
    return None

# Ensure directories exist
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
os.makedirs(app.config['GENERATED_FOLDER'], exist_ok=True)

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def save_binary_file(file_name, data):
    with open(file_name, "wb") as f:
        f.write(data)

# File cleanup functionality
def cleanup_old_files():
    """Remove files older than FILE_TTL seconds from upload and generated folders."""
    while True:
        try:
            now = time.time()
            # Clean upload folder
            for filename in os.listdir(app.config['UPLOAD_FOLDER']):
                filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
                file_mod_time = os.path.getmtime(filepath)
                if now - file_mod_time > app.config['FILE_TTL']:
                    try:
                        os.remove(filepath)
                        logger.info(f"Removed old upload file: {filename}")
                    except Exception as e:
                        logger.error(f"Failed to remove file {filename}: {e}")
            
            # Clean generated folder
            for filename in os.listdir(app.config['GENERATED_FOLDER']):
                filepath = os.path.join(app.config['GENERATED_FOLDER'], filename)
                file_mod_time = os.path.getmtime(filepath)
                if now - file_mod_time > app.config['FILE_TTL']:
                    try:
                        os.remove(filepath)
                        logger.info(f"Removed old generated file: {filename}")
                    except Exception as e:
                        logger.error(f"Failed to remove file {filename}: {e}")
                        
            # Sleep for 60 seconds before checking again
            time.sleep(60)
        except Exception as e:
            logger.error(f"Error in cleanup thread: {e}")
            time.sleep(60)  # Sleep and try again even if there was an error

def generate(input_file_path, output_file_path):
    # Create a client using your API key stored in GEMINI_API_KEY
    api_key = os.environ.get("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("API_KEYenvironment variable is not set")
    
    client = genai.Client(api_key=api_key)
    
    # Check if input file exists
    if not os.path.exists(input_file_path):
        raise FileNotFoundError(f"Input file not found: {input_file_path}")
        
    # Check if output directory is writable
    output_dir = os.path.dirname(output_file_path)
    if not os.access(output_dir, os.W_OK):
        raise PermissionError(f"Cannot write to output directory: {output_dir}")
    
    logger.info(f"Uploading file: {input_file_path}")
    # Upload the input image file
    files = [client.files.upload(file=input_file_path)]
    logger.info(f"File uploaded successfully with URI: {files[0].uri}")
    
    model = "gemini-2.0-flash-exp-image-generation"
    prompt = """
    You are a world class photo editor. You have been tasked with removing a watermark from an image in which I have accidentally added watermarks.
    First, examine the image and identify the watermark and other subjects in the image.
    Once you have identified the watermark, remove it from the image while keeping the rest of the image intact.
    If watermark is overlapping with other subjects, please ensure that you only remove the watermark and not the other subjects.
    Please ensure that the final image does not contain any visible traces of the watermark and does not touch the other subjects in the image.
    """
    
    # Create content input for the model
    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_uri(
                    file_uri=files[0].uri,
                    mime_type=files[0].mime_type,
                ),
                types.Part.from_text(text=prompt),
            ],
        )
    ]
    
    generate_content_config = types.GenerateContentConfig(
        temperature=1,
        top_p=0.97,
        top_k=45,
        max_output_tokens=8192,
        response_modalities=["image", "text"],
        safety_settings=[
            types.SafetySetting(
                category="HARM_CATEGORY_HATE_SPEECH",
                threshold="OFF",
            ),
            types.SafetySetting(
                category="HARM_CATEGORY_SEXUALLY_EXPLICIT",
                threshold="OFF"
            ),
            types.SafetySetting(
                category="HARM_CATEGORY_DANGEROUS_CONTENT",
                threshold="OFF"
            ),
            types.SafetySetting(
                category="HARM_CATEGORY_HARASSMENT",
                threshold="OFF"
            ),
            types.SafetySetting(
                category="HARM_CATEGORY_CIVIC_INTEGRITY",
                threshold="OFF"
            )
        ],
        response_mime_type="text/plain",
    )
    
    # Process the generation stream
    try:
        logger.info(f"Starting content generation with model: {model}")
        stream = client.models.generate_content_stream(
            model=model,
            contents=contents,
            config=generate_content_config,
        )
        
        got_response = False
        for chunk in stream:
            finish_reason = chunk.candidates[0].finish_reason
            if finish_reason == "IMAGE_SAFETY":
                raise Exception(
                    "🚨 Image modification was blocked due to safety restrictions. Please use different image"
                )
            if not chunk.candidates or not chunk.candidates[0].content or not chunk.candidates[0].content.parts:
                logger.info("Received empty chunk, continuing...")
                continue
                
            if chunk.candidates[0].content.parts[0].inline_data:
                logger.info("Received image data, saving to file...")
                save_binary_file(output_file_path, chunk.candidates[0].content.parts[0].inline_data.data)
                got_response = True
                break
            else:
                logger.info(f"Received text: {chunk.text}")
        
        if not got_response:
            raise Exception("No image data received from the API, please try again (it may be a temporary issue 🙈)")
            
        logger.info(f"Image generated successfully: {output_file_path}")
        return output_file_path
        
    except Exception as e:
        logger.info(f"Error during content generation: {e}")
        raise

@app.route('/login')
def login():
    # If already logged in, redirect to home
    if current_user.is_authenticated:
        return redirect('/')
    if request.args.get('auth') == 'google':
        try:
            # Generate redirect URI
            redirect_uri = url_for('callback', _external=True)
            logger.info(f"Generated redirect URI: {redirect_uri}")
            auth_url = "https://accounts.google.com/o/oauth2/v2/auth"
            client_id = os.environ.get("GOOGLE_CLIENT_ID")
            
            params = {
                "client_id": client_id,
                "redirect_uri": redirect_uri,
                "response_type": "code",
                "scope": "openid email profile",
                "access_type": "offline",
                "prompt": "consent",
                "include_granted_scopes": "true"
            }
            full_url = f"{auth_url}?{urlencode(params)}"
            logger.info(f"Initiating OAuth flow with client_id: {client_id[:8]}... and redirect_uri: {redirect_uri}")
            
            return redirect(full_url)
        except Exception as e:
            logger.error(f"Error initiating OAuth flow: {str(e)}")
            return render_template("error.html", 
                                  error=f"Error initiating OAuth flow: {str(e)}", 
                                  GA_ID=os.getenv("GA_ID", ""),
                                  current_user=current_user,
                                  config=app.config)
    return render_template('login.html', 
                          GA_ID=os.getenv("GA_ID", ""),
                          config=app.config)

@app.route('/callback')
def callback():
    try:
        auth_code = request.args.get('code')
        if auth_code and not request.args.get('state'):
            logger.info("Received direct OAuth response with code")
            client_id = os.environ.get("GOOGLE_CLIENT_ID")
            client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
            redirect_uri = url_for('callback', _external=True)
            token_url = "https://oauth2.googleapis.com/token"
            token_data = {
                "code": auth_code,
                "client_id": client_id,
                "client_secret": client_secret,
                "redirect_uri": redirect_uri,
                "grant_type": "authorization_code"
            }
            
            token_response = requests.post(token_url, data=token_data)
            
            if token_response.status_code != 200:
                error_msg = f"Error getting token: {token_response.text}"
                logger.error(error_msg)
                raise Exception(error_msg)
            
            token_json = token_response.json()
            access_token = token_json.get('access_token')
            userinfo_url = "https://www.googleapis.com/oauth2/v3/userinfo"
            headers = {"Authorization": f"Bearer {access_token}"}
            userinfo_response = requests.get(userinfo_url, headers=headers)
            
            if userinfo_response.status_code != 200:
                error_msg = f"Error getting user info: {userinfo_response.text}"
                logger.error(error_msg)
                raise Exception(error_msg)
                
            user_info = userinfo_response.json()
            
            # Map to our expected structure
            user_data = {
                'id': user_info.get('sub'),
                'name': user_info.get('name', 'Unknown User'),
                'email': user_info.get('email', ''),
                'picture': user_info.get('picture', '')
            }
        else:
            try:
                if not request.args.get('code'):
                    raise Exception("No authorization code received from Google")
                
                auth_code = request.args.get('code')
                client_id = os.environ.get("GOOGLE_CLIENT_ID")
                client_secret = os.environ.get("GOOGLE_CLIENT_SECRET")
                redirect_uri = url_for('callback', _external=True)
                token_url = "https://oauth2.googleapis.com/token"
                token_data = {
                    "code": auth_code,
                    "client_id": client_id,
                    "client_secret": client_secret,
                    "redirect_uri": redirect_uri,
                    "grant_type": "authorization_code"
                }
                
                token_response = requests.post(token_url, data=token_data)
                
                if token_response.status_code != 200:
                    error_msg = f"Error getting token: {token_response.text}"
                    logger.error(error_msg)
                    raise Exception(error_msg)
                
                token_json = token_response.json()
                access_token = token_json.get('access_token')
                
                # Get user info directly from userinfo endpoint
                userinfo_url = "https://www.googleapis.com/oauth2/v3/userinfo"
                headers = {"Authorization": f"Bearer {access_token}"}
                userinfo_response = requests.get(userinfo_url, headers=headers)
                
                if userinfo_response.status_code != 200:
                    error_msg = f"Error getting user info: {userinfo_response.text}"
                    logger.error(error_msg)
                    raise Exception(error_msg)
                
                user_info = userinfo_response.json()
                
                # Map to our expected structure
                user_data = {
                    'id': user_info.get('sub'),
                    'name': user_info.get('name', 'Unknown User'),
                    'email': user_info.get('email', ''),
                    'picture': user_info.get('picture', '')
                }
            except Exception as inner_e:
                logger.error(f"Error during token processing: {str(inner_e)}")
                raise
        logger.info(f"User successfully authenticated: {user_data.get('email')}")
        session['user_info'] = user_data
        
        # Login user
        user = User(
            id=user_data.get('id'),
            name=user_data.get('name'),
            email=user_data.get('email'),
            profile_pic=user_data.get('picture', '')
        )
        login_user(user)
        
        if 'oauth_error' in session:
            session.pop('oauth_error', None)
        
        return redirect('/')
    except Exception as e:
        logger.error(f"OAuth error in callback: {str(e)}")
        logger.error(f"OAuth error: {str(e)}")
        return redirect('/login')
    
@app.route('/direct-google-login')
def direct_google_login():
    """Alternative Google login that builds the URL directly."""
    # Google OAuth configuration
    client_id = os.environ.get("GOOGLE_CLIENT_ID")
    redirect_uri = url_for('callback', _external=True)
    auth_url = "https://accounts.google.com/o/oauth2/v2/auth"
    params = {
        "client_id": client_id,
        "redirect_uri": redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
        "access_type": "offline",
        "prompt": "consent",
        "include_granted_scopes": "true"
    }
    full_url = f"{auth_url}?{urlencode(params)}"
    logger.info(f"Manual OAuth URL: {full_url}")
    return redirect(full_url)

@app.route('/logout')
def logout():
    """User logout route."""
    session.pop('user_info', None)
    session.pop('oauth_error', None)
    logout_user()
    return redirect('/')

@app.route('/')
@login_required
def index():
    return render_template("index.html", 
                          GA_ID=os.getenv("GA_ID", ""), 
                          user=current_user,
                          config=app.config)

@app.route('/process', methods=['POST'])
@login_required
def process_image():
    if 'image' not in request.files:
        logger.info("No file part in the request")
        return redirect('/')
        
    file = request.files['image']
    if file.filename == '':
        logger.info("No file selected")
        return redirect('/')
    
    allowed_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.webp'}
    file_ext = os.path.splitext(file.filename)[1].lower()
    if file_ext not in allowed_extensions:
        logger.info(f"File type not allowed: {file_ext}")
        return render_template("error.html", error="File type not supported. Please upload a JPG, PNG, or GIF image.", GA_ID=os.getenv("GA_ID", ""), current_user=current_user, config=app.config)
    
    # Generate a unique filename to avoid collisions
    original_ext = os.path.splitext(file.filename)[1]
    unique_id = str(uuid.uuid4())
    unique_filename = unique_id + original_ext
    
    # Save the uploaded file
    upload_path = os.path.join(app.config['UPLOAD_FOLDER'], unique_filename)
    file.save(upload_path)
    
    # Define an output filename and path
    output_filename = "generated_" + unique_filename
    output_path = os.path.join(app.config['GENERATED_FOLDER'], output_filename)
    
    # Call the generate function to remove watermark
    try:
        logger.info(f"Processing upload: {upload_path}")
        logger.info(f"Output will be saved to: {output_path}")
        if not os.environ.get("GEMINI_API_KEY"):
            logger.info("API_KEYenvironment variable is not set")
            return render_template("error.html", error="API key not configured. Please set the API_KEYenvironment variable.", GA_ID=os.getenv("GA_ID", ""), current_user=current_user, config=app.config)
        
        generate(upload_path, output_path)
        
        if not os.path.exists(output_path):
            logger.info(f"Output file was not created: {output_path}")
            return render_template("error.html", error="Failed to generate output image. Please try again.", GA_ID=os.getenv("GA_ID", ""), current_user=current_user, config=app.config)
        
        logger.info(f"Successfully processed image. Original: {unique_filename}, Generated: {output_filename}")

        generated_image_data = encode_image_to_base64(output_path, mime_type="image/png")
        original_image_data = encode_image_to_base64(upload_path, mime_type="image/png")
        # Render the result page, passing URLs for both images
        return render_template(
            "result.html", 
            original_image=original_image_data,
            generated_image=generated_image_data,
            GA_ID=os.getenv("GA_ID", ""),
            current_user=current_user,
            config=app.config
        )
    except Exception as e:
        import traceback
        logger.info(f"Error processing image: {e}")
        logger.info(traceback.format_exc())
        return render_template("error.html", error=f"Error: {str(e)}", GA_ID=os.getenv("GA_ID", ""), current_user=current_user, config=app.config)

@app.route('/uploads/<filename>')
@login_required
def uploaded_file(filename):
    return send_file(os.path.join(app.config['UPLOAD_FOLDER'], filename))

@app.route('/generated/<filename>')
@login_required
def generated_file(filename):
    return send_file(os.path.join(app.config['GENERATED_FOLDER'], filename))

@app.errorhandler(413)
def too_large(e):
    return render_template("error.html", 
                          error="File is too large. Please upload an image smaller than 10MB.", 
                          GA_ID=os.getenv("GA_ID", ""),
                          current_user=current_user,
                          config=app.config), 413

@app.errorhandler(500)
def server_error(e):
    return render_template("error.html", 
                          error="An unexpected error occurred. Please try again later.", 
                          GA_ID=os.getenv("GA_ID", ""),
                          current_user=current_user,
                          config=app.config), 500

# Check for API key on startup
if __name__ == '__main__':
    if not os.environ.get("GEMINI_API_KEY"):
        logger.info("WARNING: GEMINI_API_KEY environment variable is not set!")
        logger.info("To set it, run: export GEMINI_API_KEY=your_api_key_here")
    
    if not os.environ.get("GOOGLE_CLIENT_ID") or not os.environ.get("GOOGLE_CLIENT_SECRET"):
        logger.info("WARNING: Google OAuth credentials are not set!")
        logger.info("To set them, run:")
        logger.info("export GOOGLE_CLIENT_ID=your_google_client_id_here")
        logger.info("export GOOGLE_CLIENT_SECRET=your_google_client_secret_here")
    
    # Check if tmp directories are writable
    for directory in [app.config['UPLOAD_FOLDER'], app.config['GENERATED_FOLDER']]:
        try:
            os.makedirs(directory, exist_ok=True)
            test_file = os.path.join(directory, 'test_write.txt')
            with open(test_file, 'w') as f:
                f.write('test')
            os.remove(test_file)
            logger.info(f"Directory {directory} is writable")
        except Exception as e:
            logger.info(f"WARNING: Could not write to {directory}: {e}")
    
    # Start the cleanup thread
    cleanup_thread = threading.Thread(target=cleanup_old_files, daemon=True)
    cleanup_thread.start()
    logger.info("File cleanup thread started, will remove files older than 10 minutes")
    
    app.run(debug=True)