import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from backend.api import routes
from backend.api.models import ChatMessage, Session
from backend.services.session_storage import SessionStorage


class RecordingSessionHistoryTests(unittest.TestCase):
    def test_attaching_audio_keeps_answers_saved_after_cache_snapshot(self):
        with tempfile.TemporaryDirectory() as folder:
            storage = SessionStorage(folder)
            stale = Session(id='session', title='Interview', created_at=1, updated_at=1,
                            messages=[ChatMessage(id='q1', role='user', content='First question')])
            self.assertTrue(storage.save_session(stale))
            latest = storage.load_session('session')
            latest.messages.append(ChatMessage(id='a1', role='assistant', content='First answer'))
            latest.messages.append(ChatMessage(id='q2', role='user', content='Second question'))
            self.assertTrue(storage.save_session(latest))
            voice = routes.VOICE_DIR / 'history-preservation-test.wav'
            with patch.object(routes, 'session_storage', storage), \
                 patch.object(routes, 'current_session_id', 'session'), \
                 patch.object(routes, 'current_session_cache', stale):
                routes.attach_recording_to_session('session', str(voice))
                result = storage.load_session('session')
                self.assertEqual([message.id for message in result.messages], ['q1', 'a1', 'q2'])
                self.assertIn(voice.name, result.audio_files)
                self.assertEqual(len(routes.get_current_session().messages), 3)
