
import sys
import io
import textwrap
import tempfile
import subprocess

import streamlit as st
import requests
import imageio_ffmpeg

from pathlib import Path
from google import genai
from PIL import Image, ImageOps, ImageDraw, ImageFont


# --------------------------------------------------
# 1. PAGE CONFIGURATION
# --------------------------------------------------

st.set_page_config(
    page_title="AI Content Studio",
    page_icon="🎨",
    layout="centered"
)

st.title("🎨 AI Content Studio")
st.caption("Create marketing content, promotional posters and videos using AI.")


# --------------------------------------------------
# 2. LOAD CONFIGURATION
# --------------------------------------------------

secrets_path = (
    Path(__file__).resolve().parent
    / ".streamlit"
    / "secrets.toml"
)

if sys.version_info >= (3, 11):
    import tomllib
else:
    import tomli as tomllib


try:
    with secrets_path.open("rb") as file:
        config = tomllib.load(file)

except (OSError, ValueError) as error:
    st.error(f"Cannot read configuration: {secrets_path}")
    st.error(str(error))
    st.stop()


# Check API keys
for key in ["GEMINI_API_KEY", "STABILITY_API_KEY"]:

    if not isinstance(config.get(key), str) or not config[key].strip():
        st.error(f"Missing or empty API key: {key}")
        st.info(f"Please edit: {secrets_path}")
        st.stop()


# --------------------------------------------------
# 3. SESSION STATE
# --------------------------------------------------

if "brief" not in st.session_state:
    st.session_state.brief = None

if "content" not in st.session_state:
    st.session_state.content = None

if "poster" not in st.session_state:
    st.session_state.poster = None

if "video" not in st.session_state:
    st.session_state.video = None


# --------------------------------------------------
# 4. USER INPUTS
# --------------------------------------------------

st.subheader("Campaign Details")

idea = st.text_input(
    "Your Idea",
    "Dance Creator Club",
    max_chars=70
)

audience = st.text_input(
    "Audience",
    "College Students",
    max_chars=100
)

cta = st.text_input(
    "Call to Action",
    "Join us Start Creating Better India!",
    max_chars=60
)


# Create campaign brief
brief = f"""
Idea: {idea}.
Audience: {audience}.
Call to action: {cta}.
"""


# Reset generated content when inputs change
if st.session_state.brief != brief:

    st.session_state.update(
        brief=brief,
        content=None,
        poster=None,
        video=None
    )


# Validate inputs
if not all(value.strip() for value in [idea, audience, cta]):
    st.info("Please complete all three fields.")
    st.stop()


# --------------------------------------------------
# 5. GENERATE MARKETING CONTENT USING GEMINI
# --------------------------------------------------

st.divider()
st.subheader("Step 1: Generate Marketing Content")

if st.button("1. Generate captions and script", use_container_width=True):

    try:

        with st.spinner("Gemini is writing your content..."):

            client = genai.Client(
                api_key=config["GEMINI_API_KEY"].strip()
            )

            result = client.models.generate_content(
                model=config.get(
                    "TEXT_MODEL",
                    "gemini-2.5-flash"
                ),
                contents=f"""
                {brief}

                Write the following promotional content:

                1. Instagram caption.
                2. WhatsApp promotional message.
                3. A 15-second promotional video script.

                Use only the supplied facts.
                Do not invent dates, prices or links.
                Make the content engaging and creative.
                """
            )

            if not result.text:
                raise ValueError("Gemini returned no text.")

            st.session_state.content = result.text

            st.success("Marketing content generated successfully!")

    except Exception as error:
        st.error(f"Writing failed: {error}")


# Display generated content
if st.session_state.content:

    st.subheader("Generated Marketing Content")

    st.write(st.session_state.content)

    st.download_button(
        label="Download writing",
        data=st.session_state.content,
        file_name="Campaign.txt",
        mime="text/plain"
    )


# --------------------------------------------------
# 6. GENERATE POSTER USING STABILITY AI
# --------------------------------------------------

st.divider()
st.subheader("Step 2: Generate Promotional Poster")

if st.button("2. Generate Stable Diffusion poster", use_container_width=True):

    try:

        with st.spinner("Stability AI is generating your poster..."):

            # Stability AI API request
            response = requests.post(
                "https://api.stability.ai/v2beta/stable-image/generate/sd3",

                headers={
                    "Authorization": (
                        f"Bearer {config['STABILITY_API_KEY'].strip()}"
                    ),
                    "Accept": "image/*"
                },

                files={
                    "none": ""
                },

                data={
                    "prompt": (
                        f"Create a beautiful promotional illustration "
                        f"for {idea}, designed for {audience}. "
                        "Navy blue and yellow color scheme, "
                        "professional graphic design, "
                        "modern composition, attractive lighting. "
                        "No text and no people."
                    ),

                    "model": "sd3.5-large-turbo",

                    "aspect_ratio": "2:3",

                    "output_format": "png"
                },

                timeout=(10, 90)
            )

            response.raise_for_status()

            # Open generated image
            art = Image.open(
                io.BytesIO(response.content)
            ).convert("RGB")

            # Create poster background
            poster = Image.new(
                "RGB",
                (432, 768),
                "#071D3F"
            )

            # Resize AI image
            resized_art = ImageOps.fit(
                art,
                (432, 560)
            )

            poster.paste(
                resized_art,
                (0, 0)
            )

            # Add promotional text
            draw = ImageDraw.Draw(poster)

            try:
                title_font = ImageFont.load_default(size=26)
                cta_font = ImageFont.load_default(size=20)

            except TypeError:
                title_font = ImageFont.load_default()
                cta_font = ImageFont.load_default()

            draw.multiline_text(
                (20, 580),
                textwrap.fill(idea, 25),
                font=title_font,
                fill="#FFD447",
                spacing=5
            )

            draw.multiline_text(
                (20, 690),
                textwrap.fill(cta, 32),
                font=cta_font,
                fill="white",
                spacing=4
            )

            # Save poster to memory
            output = io.BytesIO()

            poster.save(
                output,
                format="PNG"
            )

            st.session_state.update(
                poster=output.getvalue(),
                video=None
            )

            st.success("Promotional poster generated successfully!")

    except requests.Timeout:
        st.error(
            "Stability AI timed out. Please try again later."
        )

    except requests.HTTPError as error:

        st.error(
            f"Stability API returned HTTP {error.response.status_code}"
        )

        st.code(
            error.response.text[:1000],
            language="text"
        )

    except Exception as error:
        st.error(f"Poster generation failed: {error}")


# Display poster
if st.session_state.poster:

    st.subheader("Your Promotional Poster")

    st.image(
        st.session_state.poster,
        width=320
    )

    st.download_button(
        label="Download poster",
        data=st.session_state.poster,
        file_name="poster.png",
        mime="image/png"
    )


# --------------------------------------------------
# 7. EXPORT 15-SECOND PROMOTIONAL VIDEO
# --------------------------------------------------

st.divider()
st.subheader("Step 3: Export Promotional Video")

if st.button("3. Export 15-second promo video", use_container_width=True):

    if not st.session_state.poster:

        st.warning("Please generate your poster first.")

    else:

        try:

            with st.spinner("Exporting your promotional video..."):

                with tempfile.TemporaryDirectory() as folder:

                    source = Path(folder) / "poster.png"
                    target = Path(folder) / "promo.mp4"

                    # Save poster temporarily
                    source.write_bytes(
                        st.session_state.poster
                    )

                    # FFmpeg command
                    subprocess.run(
                        [
                            imageio_ffmpeg.get_ffmpeg_exe(),

                            "-y",

                            "-loop", "1",

                            "-framerate", "6",

                            "-i", str(source),

                            "-t", "15",

                            "-vf",
                            (
                                "fade=t=in:st=0:d=0.5,"
                                "fade=t=out:st=14.5:d=0.5,"
                                "format=yuv420p"
                            ),

                            "-c:v", "libx264",

                            "-preset", "ultrafast",

                            "-movflags", "+faststart",

                            str(target)
                        ],

                        check=True,
                        capture_output=True,
                        timeout=60
                    )

                    # Save generated video
                    st.session_state.video = target.read_bytes()

                    st.success("Promotional video exported successfully!")

        except subprocess.CalledProcessError as error:

            st.error("FFmpeg video export failed.")

            st.code(
                error.stderr.decode(errors="replace")[-1000:],
                language="text"
            )

        except Exception as error:

            st.error(f"Video export failed: {error}")


# Display video
if st.session_state.video:

    st.subheader("Your Promotional Video")

    st.video(
        st.session_state.video
    )

    st.download_button(
        label="Download video",
        data=st.session_state.video,
        file_name="promo.mp4",
        mime="video/mp4"
    )


# --------------------------------------------------
# 8. FOOTER
# --------------------------------------------------

st.divider()

st.caption(
    "🎨 AI Content Studio | Powered by Google Gemini "
    "and Stability AI"
)
