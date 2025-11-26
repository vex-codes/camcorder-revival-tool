from moviepy import VideoFileClip
import numpy as np
from PIL import Image, ImageEnhance, ImageDraw, ImageFilter, ImageFont
import os
import random
from datetime import datetime
import sys
import logging
import glob

# --- LOGGING SETUP ---
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# --- HELPER FUNCTIONS ---

def apply_clarity_softening(img, strength):
    """
    Applies a subtle Gaussian blur to simulate lens softening or halation.
    """
    if strength > 0:
        radius = strength / 2.5 
        img = img.filter(ImageFilter.GaussianBlur(radius))
    return img

def create_timestamp_overlay(video_size, timestamp_text, message_text=""):
    """
    Creates a transparent RGBA image with the timestamp and message.
    This is done ONCE per video to save massive processing time.
    """
    width, height = video_size
    overlay = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    
    # --- CONFIGURATION ---
    FONT_SIZE_MULTIPLIER = 0.025 # Increased from 0.018 for better readability
    CORE_COLOR = (250, 189, 90) 
    HALO_COLOR = (255, 120, 0, 180) # Increased alpha from 120 for stronger contrast
    
    font_size = int(height * FONT_SIZE_MULTIPLIER) 
    try:
        # Try Bold variant first for better legibility
        font = ImageFont.truetype("Arial Bold.ttf", font_size)
    except IOError:
        try:
            font = ImageFont.truetype("arial.ttf", font_size)
        except IOError:
            # Fallback to default, trying to approximate size
            try:
                 font = ImageFont.load_default(size=font_size)
            except TypeError:
                 # Older PIL versions don't support size in load_default
                 font = ImageFont.load_default()
    
    padding_x = int(width * 0.03)
    padding_y = int(height * 0.03)
    
    draw = ImageDraw.Draw(overlay)
    
    # --- Date Position ---
    bbox_date = draw.textbbox((0, 0), timestamp_text, font=font)
    date_text_height = bbox_date[3] - bbox_date[1]
    date_pos = (padding_x, height - date_text_height - padding_y)
    
    texts_to_draw = [(timestamp_text, date_pos, font)]

    # --- Message Position ---
    clean_message = message_text.strip()
    if clean_message:
        bbox_msg = draw.textbbox((0, 0), clean_message, font=font)
        msg_width = bbox_msg[2] - bbox_msg[0]
        msg_pos = (width - padding_x - msg_width, padding_y)
        texts_to_draw.append((clean_message, msg_pos, font))

    # --- GLOW LAYER ---
    # We draw the glow on a separate layer to blur it, then composite
    glow_layer = Image.new('RGBA', (width, height), (0, 0, 0, 0))
    glow_draw = ImageDraw.Draw(glow_layer)

    for text, (x, y), f in texts_to_draw:
        for i in range(3, 0, -1):
            glow_draw.text((x+i, y+i), text, fill=HALO_COLOR, font=f)
            glow_draw.text((x-i, y-i), text, fill=HALO_COLOR, font=f)
            glow_draw.text((x, y+i), text, fill=HALO_COLOR, font=f)
            glow_draw.text((x, y-i), text, fill=HALO_COLOR, font=f)
    
    glow_layer = glow_layer.filter(ImageFilter.GaussianBlur(1.5))
    overlay = Image.alpha_composite(overlay, glow_layer)
    
    # --- CORE TEXT ---
    draw_final = ImageDraw.Draw(overlay)
    for text, pos, f in texts_to_draw:
        draw_final.text(pos, text, fill=CORE_COLOR, font=f)
        
    return overlay

def add_noise_vectorized(arr, amount):
    """Adds random noise to a numpy array efficiently."""
    if amount <= 0:
        return arr
    
    # Generate random noise in the range [-amount, amount]
    noise = np.random.randint(-amount, amount + 1, arr.shape, dtype=np.int16)
    
    # Add noise and clip
    arr = arr.astype(np.int16) + noise
    return np.clip(arr, 0, 255).astype(np.uint8)

def apply_chromatic_aberration(arr, shift_amount=2):
    """
    Simulates chromatic aberration by shifting Red and Blue channels.
    """
    if shift_amount == 0:
        return arr
        
    # Shift Red channel left
    arr[..., 0] = np.roll(arr[..., 0], -shift_amount, axis=1)
    # Shift Blue channel right
    arr[..., 2] = np.roll(arr[..., 2], shift_amount, axis=1)
    
    return arr

def apply_jitter(arr, max_shift=2):
    """
    Simulates film gate weave (jitter) by rolling the image.
    """
    if max_shift == 0:
        return arr
        
    dx = random.randint(-max_shift, max_shift)
    dy = random.randint(-max_shift, max_shift)
    
    arr = np.roll(arr, dx, axis=1) # Shift X
    arr = np.roll(arr, dy, axis=0) # Shift Y
    
    return arr

# --- LIGHT LEAK MANAGER ---

class LightLeakManager:
    def __init__(self, leaks_dir, video_size):
        self.leaks = []
        self.active_leak_idx = -1
        self.opacity = 0.0
        self.state = 'idle' # idle, fade_in, active, fade_out
        self.duration_counter = 0
        
        # Load 5 random leaks
        all_leaks = glob.glob(os.path.join(leaks_dir, "*.jpg")) + glob.glob(os.path.join(leaks_dir, "*.png"))
        if not all_leaks:
            logger.warning("No light leaks found in 'light_leaks' folder.")
            return

        selected_paths = random.sample(all_leaks, min(5, len(all_leaks)))
        logger.info(f"Loading {len(selected_paths)} light leaks into memory...")
        
        for p in selected_paths:
            try:
                img = Image.open(p).convert('RGB').resize(video_size, Image.Resampling.BILINEAR)
                # Convert to float32 array for fast additive blending
                self.leaks.append(np.array(img, dtype=np.float32))
            except Exception as e:
                logger.warning(f"Failed to load leak {p}: {e}")

    def apply(self, frame_arr):
        if not self.leaks:
            return frame_arr
            
        # State Machine
        if self.state == 'idle':
            if random.random() < 0.02: # 2% chance per frame to start a leak
                self.state = 'fade_in'
                self.active_leak_idx = random.randint(0, len(self.leaks) - 1)
                self.opacity = 0.0
                
        elif self.state == 'fade_in':
            self.opacity += 0.05
            if self.opacity >= 0.8: # Max opacity
                self.state = 'active'
                self.duration_counter = random.randint(10, 30) # Hold for 10-30 frames
                
        elif self.state == 'active':
            self.duration_counter -= 1
            if self.duration_counter <= 0:
                self.state = 'fade_out'
                
        elif self.state == 'fade_out':
            self.opacity -= 0.03
            if self.opacity <= 0:
                self.opacity = 0.0
                self.state = 'idle'
        
        # Apply Leak if visible
        if self.opacity > 0.01:
            leak_arr = self.leaks[self.active_leak_idx]
            # Additive Blending: Frame + (Leak * Opacity)
            # We use float32 for precision then clip
            frame_float = frame_arr.astype(np.float32)
            blended = frame_float + (leak_arr * self.opacity)
            return np.clip(blended, 0, 255).astype(np.uint8)
            
        return frame_arr

# --- VECTORIZED FILTERS ---

def apply_filter_modern_fuji_sim(img):
    # PIL Adjustments
    img = ImageEnhance.Contrast(img).enhance(0.95)
    img = ImageEnhance.Brightness(img).enhance(1.05)
    img = apply_clarity_softening(img, 0)
    
    # Vectorized Pixel Manipulation
    arr = np.array(img, dtype=np.float32)
    
    # Calculate Luma: 0.299*R + 0.587*G + 0.114*B
    luma = np.dot(arr[..., :3], [0.299, 0.587, 0.114])
    luma = np.stack([luma]*3, axis=-1) # Make it (H, W, 3)
    
    # Color Shift
    # R + 15, G + 5, B - 10
    shift = np.array([15, 5, -10], dtype=np.float32)
    shifted = arr + shift
    
    # Blend with Luma (Saturation reduction/Bleach bypass effect)
    blend_factor = 0.05
    result = shifted * (1 - blend_factor) + luma * blend_factor
    
    # Clip and convert
    result = np.clip(result, 0, 255).astype(np.uint8)
    return Image.fromarray(result)

def apply_filter_terracotta_sun_sim(img):
    img = apply_clarity_softening(img, 4.0)
    img = ImageEnhance.Contrast(img).enhance(0.85)
    img = ImageEnhance.Color(img).enhance(1.35)
    
    arr = np.array(img, dtype=np.int16)
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    
    # Vectorized Blue Check
    avg_rg = (r + g) // 2
    is_blue = b > (avg_rg + 30)
    
    # Apply shifts based on mask
    r_shift = np.where(is_blue, 15, 40)
    g_shift = np.where(is_blue, -10, -5)
    b_shift = np.where(is_blue, -70, -35)
    
    arr[..., 0] += r_shift
    arr[..., 1] += g_shift
    arr[..., 2] += b_shift
    
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    
    # Add Grain (Amount 5)
    arr = add_noise_vectorized(arr, 5)
    
    return Image.fromarray(arr)

def apply_filter_portra_800_sim(img):
    img = ImageEnhance.Brightness(img).enhance(1.08)
    img = ImageEnhance.Contrast(img).enhance(0.85)
    img = ImageEnhance.Color(img).enhance(1.3)
    img = apply_clarity_softening(img, 1.5)
    
    arr = np.array(img, dtype=np.int16)
    
    # R + 19, G + 10, B - 33
    arr[..., 0] += 19
    arr[..., 1] += 10
    arr[..., 2] -= 33
    
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    
    # Grain Amount 15
    arr = add_noise_vectorized(arr, 15)
    
    return Image.fromarray(arr)

def apply_filter_reala_ace_sim(img):
    img = ImageEnhance.Brightness(img).enhance(1.0)
    img = ImageEnhance.Contrast(img).enhance(0.8)
    img = ImageEnhance.Color(img).enhance(1.2)
    img = apply_clarity_softening(img, 2)
    
    arr = np.array(img, dtype=np.int16)
    
    # R - 11, G + 10, B + 11
    arr[..., 0] -= 11
    arr[..., 1] += 10
    arr[..., 2] += 11
    
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    
    # Grain Amount 5
    arr = add_noise_vectorized(arr, 5)
    
    return Image.fromarray(arr)

def apply_filter_dreamy_negative_sim(img):
    img = ImageEnhance.Contrast(img).enhance(0.90)
    img = ImageEnhance.Color(img).enhance(1.50)
    img = apply_clarity_softening(img, 0)
    
    arr = np.array(img, dtype=np.float32)
    
    # WB Shift: R+20, B-20
    arr[..., 0] += 20
    arr[..., 2] -= 20
    
    # Luma for Shadow/Highlight shaping
    luma = np.dot(arr[..., :3], [0.299, 0.587, 0.114])
    
    # Lift Shadows (luma < 60)
    shadow_mask = luma < 60
    lift = (60 - luma) * 0.2
    lift = np.where(shadow_mask, lift, 0)
    lift = np.stack([lift]*3, axis=-1)
    arr += lift
    
    # Darken Highlights (luma > 200)
    highlight_mask = luma > 200
    darken = (luma - 200) * 0.15
    darken = np.where(highlight_mask, darken, 0)
    darken = np.stack([darken]*3, axis=-1)
    arr -= darken
    
    arr = np.clip(arr, 0, 255).astype(np.uint8)
    
    # Grain Amount 8
    arr = add_noise_vectorized(arr, 8)
    
    return Image.fromarray(arr)

# --- MAIN PROCESSING ---

def get_user_inputs():
    print("\n--- Video Vintage Filter ---")
    print("Available Filters:")
    print("1. modern_fuji_sim")
    print("2. terracotta_sun_sim")
    print("3. portra_800_sim")
    print("4. reala_ace_sim")
    print("5. dreamy_negative_sim")
    
    choice = input("Select filter (1-5) [Default: 5]: ").strip()
    filters = {
        "1": "modern_fuji_sim",
        "2": "terracotta_sun_sim",
        "3": "portra_800_sim",
        "4": "reala_ace_sim",
        "5": "dreamy_negative_sim"
    }
    filter_name = filters.get(choice, "dreamy_negative_sim")
    print(f"Selected: {filter_name}")
    
    message = input("Enter top-right message (e.g. 'REC', 'DAY 1') [Default: REC]: ").strip()
    if not message: message = "REC"
    
    print("Enter Date (Leave blank for today):")
    month = input("Month (MM): ").strip()
    day = input("Day (DD): ").strip()
    year = input("Year (YY): ").strip()
    
    now = datetime.now()
    m = month if month else now.strftime("%m")
    d = day if day else now.strftime("%d")
    y = year if year else now.strftime("%y")
    
    timestamp = f"{m}-{d}-'{y}"
    
    # --- Additional Effects Prompts ---
    print("\n--- Additional Effects ---")
    
    use_aberration = input("Enable Chromatic Aberration (Color Fringing)? (y/N) [Default: No]: ").strip().lower()
    enable_aberration = use_aberration == 'y' or use_aberration == 'yes'
    
    use_jitter = input("Enable Film Jitter (Frame Shake)? (y/N) [Default: No]: ").strip().lower()
    enable_jitter = use_jitter == 'y' or use_jitter == 'yes'

    use_leaks = input("Enable Light Leaks? (y/N) [Default: No]: ").strip().lower()
    enable_leaks = use_leaks == 'y' or use_leaks == 'yes'

    # --- Preview Mode ---
    use_preview = input("Generate 5s Preview only? (y/N) [Default: No]: ").strip().lower()
    enable_preview = use_preview == 'y' or use_preview == 'yes'
    
    return {
        "filter_name": filter_name,
        "message": message,
        "timestamp": timestamp,
        "enable_aberration": enable_aberration,
        "enable_jitter": enable_jitter,
        "enable_leaks": enable_leaks,
        "enable_preview": enable_preview
    }

if __name__ == "__main__":
    input_video_path = "input_video.mp4" 
    output_video_path = "output_video.mp4"
    
    if not os.path.exists(input_video_path):
        logger.error(f"Input file '{input_video_path}' not found.")
        print("Please place a video file named 'input_video.mp4' in this directory.")
        sys.exit(1)

    try:
        # Get Configuration
        config = get_user_inputs()
        
        filter_funcs = {
            "modern_fuji_sim": apply_filter_modern_fuji_sim,
            "terracotta_sun_sim": apply_filter_terracotta_sun_sim,
            "portra_800_sim": apply_filter_portra_800_sim,
            "reala_ace_sim": apply_filter_reala_ace_sim,
            "dreamy_negative_sim": apply_filter_dreamy_negative_sim
        }
        selected_filter = filter_funcs[config["filter_name"]]

        logger.info(f"Processing video: {input_video_path}")
        logger.info(f"Settings: {config}")
        
        clip = VideoFileClip(input_video_path)
        
        # Apply Preview Mode
        if config["enable_preview"]:
            logger.info("PREVIEW MODE: Trimming to first 5 seconds.")
            # MoviePy 2.0+ uses 'subclipped', older uses 'subclip'
            if hasattr(clip, 'subclipped'):
                clip = clip.subclipped(0, 5)
            else:
                clip = clip.subclip(0, 5)
        
        # Pre-render the timestamp overlay ONCE
        logger.info("Generating timestamp overlay...")
        overlay_img = create_timestamp_overlay(clip.size, config["timestamp"], config["message"])
        
        # Initialize Light Leak Manager
        leak_manager = None
        if config["enable_leaks"]:
            leak_manager = LightLeakManager("light_leaks", clip.size)

        def process_frame(frame):
            # 1. Convert to PIL
            img = Image.fromarray(frame)
            
            # 2. Apply Vectorized Filter
            img = selected_filter(img)
            
            # 3. Composite Overlay
            img = img.convert('RGBA')
            img = Image.alpha_composite(img, overlay_img)
            img = img.convert('RGB')
            
            # 4. Apply Final Vectorized Effects
            arr = np.array(img)
            
            if config["enable_aberration"]:
                arr = apply_chromatic_aberration(arr, shift_amount=2)
                
            if config["enable_jitter"]:
                arr = apply_jitter(arr, max_shift=1)
                
            if leak_manager:
                arr = leak_manager.apply(arr)
            
            return arr

        # Apply processing
        processed_clip = clip.image_transform(process_frame)
        
        # Write output
        try:
            logger.info("Attempting to use Apple M4 Hardware Acceleration (h264_videotoolbox)...")
            processed_clip.write_videofile(
                output_video_path, 
                audio=True, 
                threads=8, 
                codec='h264_videotoolbox',
                ffmpeg_params=['-q:v', '50'],
                logger='bar' 
            )
        except Exception as e:
            logger.warning(f"Hardware acceleration failed: {e}")
            logger.info("Falling back to standard libx264 encoding...")
            processed_clip.write_videofile(
                output_video_path, 
                audio=True, 
                threads=4, 
                codec='libx264'
            )
        
        logger.info(f"Done! Saved to: {output_video_path}")
        
    except KeyboardInterrupt:
        logger.warning("\nProcessing cancelled by user.")
        sys.exit(0)
    except Exception as e:
        logger.critical(f"An unexpected error occurred: {e}", exc_info=True)
        sys.exit(1)
