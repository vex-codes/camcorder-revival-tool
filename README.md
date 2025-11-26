# 📼 Camcorder Revival: Vintage Video Processor

<div align="center">

</div>

## 🔥 The Retro Workflow

The **Camcorder Revival Tool** is the ultimate utility for transforming clean, modern video footage into an authentic vintage recording, simulating the look and physical flaws of old tape and film cameras. It leverages high-performance, NumPy-vectorized filters and combines them with temporal and structural video artifacts.

**Highly Optimized for macOS:** The tool utilizes the `h264_videotoolbox` codec to offload video encoding to the **Apple Silicon M4/M3/M2/M1 Media Engine**, ensuring lightning-fast processing and efficient resource use. 

## ✨ Features That Define Analog

| Feature | Description | Impact | 
 | ----- | ----- | ----- | 
| **Film Simulations** | Custom-tuned color and grain profiles (Portra, Fuji, Terracotta Sun) utilizing vectorized math for speed. | Authentic, warm color grade and texture. | 
| **Tape Jitter** | Random, subtle vertical/horizontal shifting (`np.roll`) of the frame array. | Simulates unstable tape mechanics. | 
| **Light Leaks/Scratches** | Randomly loaded and composited overlays applied during runtime. | Adds organic light flares and physical film flaws. | 
| **Chromatic Aberration** | R and B color channels are slightly shifted relative to G. | Simulates cheap, low-quality optics. | 
| **Time Stamp** | Retro, glowing, fixed-position time/date overlay, generated once. | Essential camcorder aesthetic. | 
| **Performance** | Hardware-accelerated encoding via **VideoToolbox**. | Fastest possible encoding on macOS. | 

## ⚙️ Setup and Usage

### Prerequisites

You must have the following Python packages installed:
`pip install moviepy numpy pillow tqdm pydub`

**Ensure FFmpeg is installed and accessible in your system path (moviepy often handles this).**

### 1️⃣ Project Structure & Input File

The script is configured to look for the input video file and light leak assets in specific locations:

1.  **Input Video:** Place the video you wish to process in the same directory as the script and name it exactly: `input_video.mp4`
2.  **Light Leaks:** If you choose to enable light leaks, create a folder named `light_leaks` in the same directory and place your `.jpg` or `.png` leak assets inside it.

### 2️⃣ Interactive Run

The script is fully interactive and will prompt you for all settings (filter choice, timestamp, and effects) upon execution.

```bash
python video_vintage.py
```

The tool will then guide you through selecting a film simulation:

* `modern_fuji_sim`
* `terracotta_sun_sim`
* `portra_800_sim`
* `reala_ace_sim`
* `dreamy_negative_sim`

It will prompt you for the desired message and date for the timestamp, and then ask if you want to enable Chromatic Aberration, Film Jitter, and Light Leaks. The output file will be saved as `output_video.mp4`.

## 🚀 Optimization and Performance

This tool is optimized specifically for speed and quality:

1. **M4 Acceleration:** The `h264_videotoolbox` codec is used to leverage Apple's hardware, reducing CPU load and export time dramatically.

2. **Vectorized Processing:** All image filter work (color grading, noise addition) is done efficiently in NumPy before being passed to the video pipeline.

## 🤝 Contribution

We welcome contributions to expand the range of artifacts and improve performance!

**Areas to explore:**

* Adding **Audio Simulation** (hiss/static generator).

* Implementing **Shadow/Highlight** specific color grading (Luma masking).

* Procedural **VHS tracking errors** (horizontal tearing).
