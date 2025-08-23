import io
import sys

from googleapiclient.http import MediaIoBaseDownload

from src.lib.google_drive.service import *
from src.lib.error_management.service import handle
from src.utils.common import get_config_value
from src.utils.logging import *


def restore_backup(latest_date):
    drive = GoogleDrive()

    backup_files_args = {
        "q": "'%s' in parents" % drive.backup_dir_id,
        "fields": "nextPageToken, files(id, name)",
        "pageSize": 1000,
    }
    backup_files = drive.get_files(backup_files_args)
    get_revisions_args = {"fields": "revisions(id, modifiedTime)"}
    drive.get_target_revisions(backup_files, get_revisions_args, latest_date)

    os.makedirs(drive.restore_dir, exist_ok=True)

    restored = []
    for file in backup_files:
        file_name = file.get("name")
        rev = file["revision"]

        try:
            media_request = drive.drive.revisions().get_media(
                fileId=file.get("id"), revisionId=rev.get("id")
            )
            byte_descriptor = io.BytesIO()
            downloader = MediaIoBaseDownload(
                byte_descriptor, media_request, chunksize=pow(10, 8)
            )

            done = False
            print_and_log("Downloading %s" % file_name, info)
            while done is False:
                status, done = downloader.next_chunk(num_retries=5)
                if done:
                    print_and_log("  Done!", info)
                else:
                    print_and_log("  %d%%" % int(status.progress() * 100), info)

            with open("%s/%s" % (drive.restore_dir, file_name), "wb") as f:
                f.write(byte_descriptor.getbuffer())

        except Exception as e:
            msg = "Error occurred while downloading %s" % file_name
            handle(e, msg, print_and_log)
            continue

        restored.append(file)

    restored_dict = {rev.get("id"): rf.to_json() for rf in restored}
    with open("%s/backup_progress.json" % get_config_value(["DATA", "ROOT"]), "w") as f:
        json.dump(restored_dict, f, indent=2)


if __name__ == "__main__":
    restore_backup(datetime.strptime(sys.argv[1], TS_FORMAT))
