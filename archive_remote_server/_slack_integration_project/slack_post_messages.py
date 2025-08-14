from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
import ssl


class SlackPostMessages:
    def __init__(self, slack_token, channel_id):
        """
        Initializes the SlackPostMessages class.

        :param slack_token: Slack bot token
        :param channel_id: Slack channel ID to post messages to
        """
        self.channel_id = channel_id
        self.client = WebClient(token=slack_token, ssl=ssl._create_unverified_context())

    def post_message(self, message):
        """
        Posts a plain text message to the specified Slack channel.

        :param message: Text message to be posted
        """
        try:
            self.client.chat_postMessage(channel=self.channel_id, text=message)
            print("Message posted successfully!")
        except SlackApiError as e:
            print(f"Slack API Error: {e.response['error']}")

    def post_image(self, image_path, spotter_id, file_name):
        """
        Posts an image to the Slack channel with a dynamic title.

        :param image_path: Path to the image file
        :param spotter_id: SPOT ID for the image
        :param file_name: Name of the image file
        """
        try:
            title = f"SPOT ID: {spotter_id}, File: {file_name}"
            response = self.client.files_upload_v2(
                channel=self.channel_id,
                file=image_path,
                title=title
            )
            #print(f"Image uploaded successfully! Response: {response.data}")
            print(f"Image uploaded successfully: {file_name}")
        except SlackApiError as e:
            print(f"Slack API Error: {e.response['error']}")
