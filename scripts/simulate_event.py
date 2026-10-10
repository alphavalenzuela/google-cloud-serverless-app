"""Local test utility to simulate Cloud Storage upload events and trigger the Cloud Run endpoint."""

import argparse
import base64
import json
import sys
from datetime import datetime, timezone
import requests


def build_gcs_notification(bucket: str, filename: str, content_type: str, size: int) -> dict:
    """Constructs a simulated GCS OBJECT_FINALIZE notification payload."""
    now_iso = datetime.now(timezone.utc).isoformat()
    return {
        "bucket": bucket,
        "name": filename,
        "contentType": content_type,
        "size": size,
        "generation": str(int(datetime.now().timestamp() * 1000000)),
        "metageneration": "1",
        "timeCreated": now_iso,
        "updated": now_iso,
    }


def build_pubsub_push_envelope(notification_dict: dict, topic: str = "doc-upload-events") -> dict:
    """Wraps GCS notification dictionary into a Pub/Sub Push subscription HTTP body."""
    raw_json = json.dumps(notification_dict)
    b64_data = base64.b64encode(raw_json.encode("utf-8")).decode("utf-8")

    return {
        "message": {
            "data": b64_data,
            "attributes": {
                "bucketId": notification_dict["bucket"],
                "eventType": "OBJECT_FINALIZE",
                "objectId": notification_dict["name"],
                "objectGeneration": notification_dict["generation"],
            },
            "messageId": f"local-msg-{int(datetime.now().timestamp())}",
            "publishTime": datetime.now(timezone.utc).isoformat(),
        },
        "subscription": f"projects/local-dev/subscriptions/{topic}-push-sub",
    }


def main():
    parser = argparse.ArgumentParser(description="Simulate GCS upload and send to local Cloud Run service.")
    parser.add_argument("--url", default="http://localhost:8080/process-event", help="Target endpoint URL")
    parser.add_argument("--bucket", default="raw-documents", help="Simulated bucket name")
    parser.add_argument("--file", default="invoices/2026/sample_vendor_invoice.pdf", help="Document filename")
    parser.add_argument("--content-type", default="application/pdf", help="Document MIME type")
    parser.add_argument("--size", type=int, default=34200, help="Document size in bytes")

    args = parser.parse_args()

    print(f"[*] Crafting simulated event for: {args.bucket}/{args.file} ({args.size} bytes)")
    notification = build_gcs_notification(args.bucket, args.file, args.content_type, args.size)
    payload = build_pubsub_push_envelope(notification)

    print(f"[*] Sending HTTP POST to {args.url} ...")
    try:
        response = requests.post(
            args.url,
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10,
        )
        print(f"[+] Status Code: {response.status_code}")
        print("[+] Response Body:")
        print(json.dumps(response.json(), indent=2))
    except requests.exceptions.ConnectionError:
        print(f"[-] Error: Could not connect to {args.url}. Is the service running on port 8080?")
        sys.exit(1)
    except Exception as e:
        print(f"[-] Request failed: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
