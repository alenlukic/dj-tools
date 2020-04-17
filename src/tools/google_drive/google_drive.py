from collections import ChainMap
from datetime import datetime
import io
import json
import pickle
import os.path

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request

from src.definitions.common import CONFIG
from src.utils.errors import handle_error
from src.utils.logging import *


class GDResource:
    def __init__(self, gd_resource):
        self.gd_resource = gd_resource

    def get(self, attr):
        if self.gd_resource is None:
            return None

        return self.gd_resource.get(attr)

    def set(self, attr, val):
        if self.gd_resource is None:
            self.gd_resource = {}

        self.gd_resource[attr] = val

    def to_json(self):
        return json.dumps(self, default=lambda obj: self._serializer(obj))

    def _serializer(self, obj):
        if obj is None:
            return 'null'

        if type(obj) == datetime:
            return obj.timestamp()

        try:
            return obj.__dict__
        except Exception:
            return str(obj)


class GoogleDrive:
    def __init__(self):
        # If modifying these scopes, delete the pickle file first
        self.scopes = ['https://www.googleapis.com/auth/drive']
        self.creds_file = CONFIG['GOOGLE_DRIVE']['CREDENTIALS']
        self.pickle_file = CONFIG['GOOGLE_DRIVE']['PICKLE']
        self.backup_dir_id = CONFIG['GOOGLE_DRIVE']['BACKUP_DIR_ID']
        self.restore_dir = CONFIG['BACKUP_RESTORE_MUSIC_DIR']
        self.drive = build('drive', 'v3', credentials=self._get_creds())

    def _get_creds(self):
        # Load existing creds if they exist
        if os.path.exists(self.pickle_file):
            with open(self.pickle_file, 'rb') as token:
                creds = pickle.load(token)

        # Refresh token if needed
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            # Create and save the credentials
            flow = InstalledAppFlow.from_client_secrets_file(self.pickle_file, self.scopes)
            creds = flow.run_local_server(port=0)
            with open(self.pickle_file, 'wb') as token:
                pickle.dump(creds, token)

        return creds

    def get_backup_files(self):
        query_args = {
            'q': '\'%s\' in parents' % self.backup_dir_id,
            'fields': 'nextPageToken, files(id, name)',
            'pageSize': 1000
        }
        request = self.drive.files().list(**query_args)
        results = request.execute()

        files = [GDResource(r) for r in results.get('files', [])]
        num_files = len(files)
        print_and_log('Retrieved %d files (%d total)' % (num_files, num_files), info)

        next_page_token = results.get('nextPageToken')
        if next_page_token is not None:
            files.extend(self._get_paged_files(next_page_token, query_args, num_files))

        return files

    def _get_paged_files(self, next_page_token, query_args, prev_file_count=0):
        files = []

        cur_token = next_page_token
        total_files = prev_file_count
        while cur_token is not None:
            args = dict(ChainMap(query_args, {'pageToken': cur_token}))
            request = self.drive.files().list(**args)
            results = request.execute()

            result_files = results.get('files', [])
            num_results = len(result_files)
            total_files += num_results

            print_and_log('Retrieved %d files (%d total)' % (num_results, total_files), info)

            files.extend([GDResource(r) for r in result_files])
            cur_token = results.get('nextPageToken')

        return files

    def get_target_revisions(self, files, query_args, latest_date):
        for file in files:
            args = dict(ChainMap(query_args, {'fileId': file.get('id')}))
            revisions = self.drive.revisions().list(**args).execute().get('revisions', [])
            revs = [{'id': r['id'], 'modifiedTime': datetime.strptime(
                r['modifiedTime'], '%Y-%m-%dT%H:%M:%S.%fZ')} for r in revisions]
            rev = sorted([r for r in revs if r['modifiedTime'] <= latest_date], key=lambda v: v['modifiedTime'])[-1]

            file.set('revision', GDResource(rev))
