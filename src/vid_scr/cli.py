import argparse
import os

import cv2
from PIL import Image

VIDEO_EXTENSIONS = {
    '.mp4',
    '.mov',
    '.avi',
    '.mkv',
    '.flv',
    '.wmv',
    '.webm',
    '.mpeg',
    '.mpg',
    '.m4v',
    '.3gp',
    '.3g2',
    '.ts',
    '.ogv',
    '.m2ts',
    '.mts',
}


def is_supported_video_file(path):
    _, ext = os.path.splitext(path)
    return ext.lower() in VIDEO_EXTENSIONS


def collect_video_files(root_path):
    video_files = []
    with os.scandir(root_path) as entries:
        for entry in sorted(entries, key=lambda e: e.name):
            if entry.is_file() and is_supported_video_file(entry.name):
                video_files.append(entry.path)
            elif entry.is_dir():
                with os.scandir(entry.path) as sub_entries:
                    for sub_entry in sorted(sub_entries, key=lambda e: e.name):
                        if sub_entry.is_file() and is_supported_video_file(sub_entry.name):
                            video_files.append(sub_entry.path)
    return sorted(video_files)


def ensure_output_directory(path):
    target = path or os.getcwd()
    os.makedirs(target, exist_ok=True)
    return target


def generate_timestamps(args, duration):
    if args.count is not None:
        capture_count = args.count
        if capture_count == 1:
            midpoint = duration / 2 if duration else 0
            return [midpoint]
        return [
            (i / (capture_count - 1)) * duration
            for i in range(capture_count)
        ]

    interval = args.interval
    capture_slots = int(duration // interval) + 1
    timestamps = [i * interval for i in range(max(1, capture_slots))]

    if duration > 0 and timestamps:
        last_capture = timestamps[-1]
        if abs(last_capture - duration) > 1e-6:
            timestamps.append(duration)

    return timestamps


def process_single_video(video_path, args, output_dir):
    print(f"Processing {video_path}...")

    cap = cv2.VideoCapture(video_path)
    try:
        if not cap.isOpened():
            print("Error: Could not open video file.")
            return False

        fps = cap.get(cv2.CAP_PROP_FPS)
        frame_count = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        if fps <= 0 or frame_count <= 0:
            print("Error: Unable to read video metadata.")
            return False

        duration = frame_count / fps
        timestamps = generate_timestamps(args, duration)

        if args.limit is not None:
            timestamps = timestamps[:args.limit]

        output_directory = ensure_output_directory(output_dir)
        screenshots = []
        for index, time_in_seconds in enumerate(timestamps):
            frame_number = min(int(round(time_in_seconds * fps)), frame_count - 1)
            cap.set(cv2.CAP_PROP_POS_FRAMES, frame_number)
            ret, frame = cap.read()

            if not ret:
                print(f"Warning: Unable to read frame at {time_in_seconds:.2f}s in {video_path}")
                continue

            if args.size:
                height, width, _ = frame.shape
                if width > height:
                    new_width = args.size
                    new_height = int(height * (new_width / width))
                else:
                    new_height = args.size
                    new_width = int(width * (new_height / height))
                frame = cv2.resize(frame, (new_width, new_height))

            video_filename = os.path.basename(video_path)
            screenshot_path = os.path.join(output_directory, f"{video_filename}_screenshot_{index + 1}.{args.format}")
            if cv2.imwrite(screenshot_path, frame):
                screenshots.append(screenshot_path)
                print(f"Saved screenshot to {screenshot_path}")
            else:
                print(f"Warning: Failed to write screenshot to {screenshot_path}")

        if args.merge and screenshots:
            print("Merging screenshots...")
            images = [Image.open(s) for s in screenshots]
            try:
                widths, heights = zip(*(img.size for img in images))

                num_images = len(images)
                num_cols = int(num_images ** 0.5) or 1
                num_rows = (num_images + num_cols - 1) // num_cols

                max_width = max(widths)
                max_height = max(heights)
                total_width = max_width * num_cols
                total_height = max_height * num_rows

                merged_image = Image.new('RGB', (total_width, total_height))

                x_offset = 0
                y_offset = 0
                for idx, img in enumerate(images):
                    merged_image.paste(img, (x_offset, y_offset))
                    x_offset += max_width
                    if (idx + 1) % num_cols == 0:
                        x_offset = 0
                        y_offset += max_height

                video_filename = os.path.basename(video_path)
                merged_image_path = os.path.join(output_directory, f"{video_filename}_merged.{args.format}")
                merged_image.save(merged_image_path)
                print(f"Saved merged screenshot to {merged_image_path}")
            finally:
                for img in images:
                    img.close()

        print("Done.")
        if not screenshots:
            print(f"Warning: No screenshots were saved for {video_path}.")
        return True
    finally:
        cap.release()


def main():
    parser = argparse.ArgumentParser(description='Capture thumbnails from a video at regular time intervals.')
    parser.add_argument('video_file', help='The video file to process.')
    parser.add_argument('--interval', type=float, default=10, help='Time between captured frames in seconds.')
    parser.add_argument('--output', default=None, help='Directory where thumbnails will be written. Defaults to the video file directory when not provided.')
    parser.add_argument('--merge', action='store_true', help='If provided, produce a merged contact-sheet/combined image from the captured thumbnails.')
    parser.add_argument('--size', type=int, help='Constrain the longest side of the output image to a specific length in pixels, while maintaining the original aspect ratio.')
    parser.add_argument('--count', type=int, help='Number of screenshots to capture.')
    parser.add_argument('--format', type=str, default='jpeg', choices=['png', 'jpeg', 'jpg', 'webp'], help='Image format for the thumbnails.')
    parser.add_argument('--limit', type=int, help='Maximum number of screenshots to keep, prioritizing the earliest captures.')

    args = parser.parse_args()

    if args.limit is not None and args.limit <= 0:
        print("Error: --limit must be a positive integer.")
        return

    if args.count is not None and args.count <= 0:
        print("Error: --count must be a positive integer.")
        return

    if args.count is None and args.interval <= 0:
        print("Error: --interval must be a positive number.")
        return

    input_path = args.video_file

    if not os.path.exists(input_path):
        print(f"Error: Input path not found at {input_path}")
        return

    if os.path.isdir(input_path):
        video_files = collect_video_files(input_path)
        if not video_files:
            print(f"No video files found in directory {input_path}")
            return
    else:
        if not os.path.isfile(input_path):
            print(f"Error: {input_path} is not a valid file.")
            return
        video_files = [input_path]

    base_output_dir = args.output
    if base_output_dir is not None:
        ensure_output_directory(base_output_dir)

    processed_any = False
    for video_file in video_files:
        output_dir = base_output_dir if base_output_dir is not None else os.path.dirname(video_file) or os.getcwd()
        success = process_single_video(video_file, args, output_dir)
        processed_any = processed_any or success

    if not processed_any:
        print("No videos were processed successfully.")


if __name__ == '__main__':
    main()
