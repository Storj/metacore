import json
import os.path
import unittest
from hashlib import sha256
from io import BytesIO

import storj
from database import files
from error_codes import *

__author__ = 'karatel'


class UploadFileCase(unittest.TestCase):
    """
    Test uploading files to the Node.
    """

    url = '/api/files/'

    def setUp(self):
        """
        Switch to test config.
        Remember initial records in the 'files' table.
        Remember initial files set in the Upload Dir.
        """
        self.app = storj.app
        self.app.config['TESTING'] = True
        self.files = set(tuple(_) for _ in files.select().execute())
        self.stored_files = set(os.listdir(self.app.config['UPLOAD_FOLDER']))

        self.file_data = b'some data'
        self.valid_hash = sha256(self.file_data).hexdigest()
        self.file_saving_path = os.path.join(
            self.app.config['UPLOAD_FOLDER'], self.valid_hash
        )

    def tearDown(self):
        """
        Remove new records form the 'files' table.
        Remove new files from Upload Dir.
        """
        files.delete().where(
            files.c.id not in (_[0] for _ in self.files)
        ).execute()

        added_files = set(
            os.listdir(self.app.config['UPLOAD_FOLDER'])
        ) - self.stored_files

        for filename in added_files:
            os.unlink(os.path.join(self.app.config['UPLOAD_FOLDER'], filename))

    def make_request(self, data):
        """
        Make a common request for this Test Case. Get a response.
        :return: Response
        """
        with self.app.test_client() as c:
            response = c.post(
                path=self.url,
                data=data,
                content_type='multipart/form-data'
            )

        return response

    def test_success_upload(self):
        """
        Upload file with all valid data.
        """
        send_data = {
            'data_hash': sha256(self.file_data).hexdigest(),
            'file_data': (BytesIO(self.file_data), 'test_file'),
            'file_role': '000'
        }

        response = self.make_request(send_data)

        self.assertEqual(201, response.status_code,
                         "'Created' status code is expected.")
        self.assertEqual('application/json', response.content_type,
                         "Has to be a JSON-response.")

        self.assertDictEqual(
            {'data_hash': send_data['data_hash'],
             'file_role': send_data['file_role']},
            json.loads(response.data.decode()),
            "Unexpected response data."
        )

        uploaded_file_record = files.select(
            files.c.hash == send_data['data_hash']
        ).execute().first()

        self.assertIsNotNone(uploaded_file_record,
                             "File record does not exist in the table.")

        self.assertSetEqual(
            self.files | {tuple(uploaded_file_record)},
            set(tuple(_) for _ in files.select().execute()),
            "Only new record has to be inserted in the database. "
            "No other changes."
        )

        try:
            with open(self.file_saving_path, 'rb') as stored_file:
                self.assertEqual(
                    self.file_data, stored_file.read(),
                    "Stored file data does not match with uploaded one."
                )
        except FileNotFoundError:
            self.assertTrue(False, 'Uploaded file is not saved.')

    def test_invalid_hash(self):
        """
        Try to upload file with invalid SHA-256 hash.
        """
        send_data = {
            'data_hash': 'invalid hash',
            'file_data': (BytesIO(self.file_data), 'test_file'),
            'file_role': '000'
        }

        response = self.make_request(send_data)

        self.assertEqual(400, response.status_code,
                         "Response has to be marked as 'Bad Request'.")
        self.assertEqual('application/json', response.content_type,
                         "Has to be a JSON-response.")

        self.assertDictEqual(
            {'error_code': ERR_INVALID_HASH},
            json.loads(response.data.decode()),
            "Unexpected response data."
        )

        self.assertSetEqual(
            self.files,
            set(tuple(_) for _ in files.select().execute()),
            "Database has to be unchanged."
        )

        self.assertFalse(os.path.exists(self.file_saving_path),
                         "File should not be saved.")


if __name__ == '__main__':
    unittest.main()
