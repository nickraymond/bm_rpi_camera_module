# import argparse
# 
# from parsing_camera_API import ParsingCameraAPI
# from slack_post_messages import SlackPostMessages
# from datetime import datetime, timedelta, timezone
# import os
import argparse
from datetime import datetime, timedelta, timezone
from slack_post_messages import SlackPostMessages
from parsing_camera_API import ParsingCameraAPI
import os

from config import CAMERA_API_TOKEN, SLACK_BOT_TOKEN, SLACK_CHANNEL_ID, SPOTTER_IDS


def get_time_range(hours_back=2):
    """Calculate the start and end times in UTC."""
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=hours_back)
    return start_time.isoformat(timespec="seconds"), end_time.isoformat(timespec="seconds")


def get_time_range(hours_back=2):
    """Get the start and end times in UTC."""
    end_time = datetime.now(timezone.utc)
    start_time = end_time - timedelta(hours=hours_back)
    return start_time.isoformat(timespec="seconds"), end_time.isoformat(timespec="seconds")

def main():
    # Parse command-line arguments
    arg_parser = argparse.ArgumentParser(description="Controller app for Spotter API and Slack integration.")
    arg_parser.add_argument(
        "--start_time",
        type=str,
        help="Manual start time in ISO 8601 format (e.g., '2025-01-01T00:00:00+00:00')."
    )
    arg_parser.add_argument(
        "--end_time",
        type=str,
        help="Manual end time in ISO 8601 format (e.g., '2025-01-01T02:00:00+00:00')."
    )
    args = arg_parser.parse_args()

    # Determine start and end times
    if args.start_time and args.end_time:
        start_time = args.start_time
        end_time = args.end_time
        print(f"Manual start and end times provided:\n Start: {start_time}\n End:   {end_time}")
    else:
        start_time, end_time = get_time_range(hours_back=2)
        print(f"Using default time range:\n Start: {start_time}\n End:   {end_time}")

    # Initialize Slack client
    slack_client = SlackPostMessages(slack_token=SLACK_BOT_TOKEN, channel_id=SLACK_CHANNEL_ID)

    # Initialize the CameraAPIParser
    camera_parser = ParsingCameraAPI(token=CAMERA_API_TOKEN)

    # Fetch and process images
    saved_images = camera_parser.parse_camera_data(
        spotter_ids=SPOTTER_IDS,
        start_date=start_time,
        end_date=end_time
    )

    # Handle results
    if not saved_images:
        no_images_message = (
            f"Executed on Raspberry Pi\n"
            f"Start Time (UTC): {start_time}\n"
            f"End Time (UTC):  {end_time}\n"
            f"\nNo images obtained."
        )
        slack_client.post_message(no_images_message)
    else:
        # Count and display unique images
        unique_images = set(image["file_path"] for image in saved_images)
        num_unique_images = len(unique_images)

        yes_images_message = (
            f"Executed on Raspberry Pi\n"
            f"Start Time (UTC): {start_time}\n"
            f"End Time (UTC):  {end_time}\n"
            f"\nThere are {num_unique_images} unique images."
        )
        slack_client.post_message(yes_images_message)

        # Post images to Slack
        for image in saved_images:
            slack_client.post_image(
                image_path=image["file_path"],
                spotter_id=image["spotter_id"],
                file_name=os.path.basename(image["file_path"])
            )

if __name__ == "__main__":
    main()
