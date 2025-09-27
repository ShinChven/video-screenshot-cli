import argparse
import os
import cv2
from PIL import Image

def main():
    parser = argparse.ArgumentParser(description='Capture thumbnails from a video at regular time intervals.')
    parser.add_argument('video_file', help='The video file to process.')
    parser.add_argument('--interval', type=float, default=10, help='Time between captured frames in seconds.')
    parser.add_argument('--output', default=os.getcwd(), help='Directory where thumbnails will be written.')
    parser.add_argument('--merge', action='store_true', help='If provided, produce a merged contact-sheet/combined image from the captured thumbnails.')
    parser.add_argument('--size', type=int, help='Constrain the longest side of the output image to a specific length in pixels, while maintaining the original aspect ratio.')
    parser.add_argument('--number', type=int, help='Number of screenshots to capture.')
    parser.add_argument('--format', type=str, default='jpeg', choices=['png', 'jpeg', 'jpg', 'webp'], help='Image format for the thumbnails.')

    args = parser.parse_args()

    if args.output == os.getcwd():
        args.output = os.path.dirname(args.video_file)

    if not os.path.exists(args.video_file):
        print(f"Error: Video file not found at {args.video_file}")
        return

    if not os.path.exists(args.output):
        os.makedirs(args.output)

    print(f"Processing {args.video_file}...")

    cap = cv2.VideoCapture(args.video_file)
    if not cap.isOpened():
        print("Error: Could not open video file.")
        return

    fps = cap.get(cv2.CAP_PROP_FPS)
    frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    if fps <= 0 or frame_count <= 0:
        print("Error: Unable to read video metadata.")
        return

    duration = frame_count / fps

    if args.number:
        if args.number <= 0:
            print("Error: --number must be a positive integer.")
            return
        capture_count = args.number
        if capture_count == 1:
            midpoint = duration / 2 if duration else 0
            timestamps = [midpoint]
        else:
            timestamps = [
                (i / (capture_count - 1)) * duration
                for i in range(capture_count)
            ]
    else:
        if args.interval <= 0:
            print("Error: --interval must be a positive number.")
            return
        interval = args.interval
        timestamps = [i * interval for i in range(int(duration / interval))]

    screenshots = []
    for i, time_in_seconds in enumerate(timestamps):
        frame_number = min(int(round(time_in_seconds * fps)), frame_count - 1)
        cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
        ret, frame = cap.read()

        if ret:
            if args.size:
                height, width, _ = frame.shape
                if width > height:
                    new_width = args.size
                    new_height = int(height * (new_width / width))
                else:
                    new_height = args.size
                    new_width = int(width * (new_height / height))
                frame = cv2.resize(frame, (new_width, new_height))

            video_filename = os.path.basename(args.video_file)
            screenshot_path = os.path.join(args.output, f"{video_filename}_screenshot_{i + 1}.{args.format}")
            cv2.imwrite(screenshot_path, frame)
            screenshots.append(screenshot_path)
            print(f"Saved screenshot to {screenshot_path}")

    cap.release()

    if args.merge and screenshots:
        print("Merging screenshots...")
        images = [Image.open(s) for s in screenshots]
        widths, heights = zip(*(i.size for i in images))

        # Calculate grid size
        num_images = len(images)
        num_cols = int(num_images**0.5)
        num_rows = (num_images + num_cols - 1) // num_cols

        total_width = max(widths) * num_cols
        total_height = max(heights) * num_rows

        merged_image = Image.new('RGB', (total_width, total_height))

        x_offset = 0
        y_offset = 0
        for i, img in enumerate(images):
            merged_image.paste(img, (x_offset, y_offset))
            x_offset += max(widths)
            if (i + 1) % num_cols == 0:
                x_offset = 0
                y_offset += max(heights)

        video_filename = os.path.basename(args.video_file)
        merged_image_path = os.path.join(args.output, f"{video_filename}_merged.{args.format}")
        merged_image.save(merged_image_path)
        print(f"Saved merged screenshot to {merged_image_path}")

    print("Done.")

if __name__ == '__main__':
    main()
