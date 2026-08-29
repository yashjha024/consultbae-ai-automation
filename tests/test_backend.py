import math
import sqlite3
import tempfile
import unittest
import wave
from pathlib import Path

from consultbae.audio import AudioAnalysisError, analyze_audio
from consultbae.ingest import ingest
from consultbae.normalization import normalize_city, normalize_email, normalize_name, normalize_phone, normalize_status

DATA = Path(r"C:\Users\yashj\Downloads")


class NormalizationTests(unittest.TestCase):
    def test_email_and_phone(self):
        self.assertEqual(normalize_email(" ISHA.CHOPRA95@MAILTEST.EXAMPLE.ORG "), "isha.chopra95@mailtest.example.org")
        self.assertIsNone(normalize_email("not-an-email"))
        self.assertEqual(normalize_phone("09000000287"), "+919000000287")
        self.assertEqual(normalize_phone("+91-9000000131"), "+919000000131")
        self.assertIsNone(normalize_phone("123"))

    def test_name_city_status(self):
        self.assertEqual(normalize_name(" R. Verma "), "r verma")
        self.assertEqual(normalize_city("bangalore"), "bengaluru")
        self.assertEqual(normalize_city("New Delhi"), "delhi ncr")
        self.assertEqual(normalize_status("Y"), "verified")


@unittest.skipUnless(DATA.exists(), "assignment source files not available")
class IngestionTests(unittest.TestCase):
    def test_ingestion_is_idempotent_and_conservative(self):
        with tempfile.TemporaryDirectory() as directory:
            db = Path(directory) / "test.sqlite3"
            first, second = ingest(db, DATA), ingest(db, DATA)
            self.assertEqual(second["new_people"], 0)
            self.assertEqual(second["rows"], 105)
            conn = sqlite3.connect(db)
            try:
                self.assertEqual(conn.execute("SELECT count(*) FROM source_records").fetchone()[0], 105)
                self.assertEqual(conn.execute("SELECT count(*) FROM source_records WHERE valid=0").fetchone()[0], 3)
                # Deepak Nair records stay separate: they only share a name.
                self.assertEqual(conn.execute("SELECT count(*) FROM persons WHERE canonical_name='Deepak Nair'").fetchone()[0], 2)
                # R. Verma and Rohit Verma merge only because their email/phone agree.
                self.assertEqual(conn.execute("SELECT count(*) FROM persons WHERE canonical_name IN ('R. Verma','Rohit Verma')").fetchone()[0], 1)
                self.assertEqual(first["invalid"], 3)
            finally:
                conn.close()


class AudioTests(unittest.TestCase):
    def test_wav_metadata_and_corrupt_file(self):
        with tempfile.TemporaryDirectory() as directory:
            good, bad = Path(directory) / "tone.wav", Path(directory) / "bad.wav"
            with wave.open(str(good), "wb") as f:
                f.setnchannels(1); f.setsampwidth(2); f.setframerate(8000)
                f.writeframes(b"\0\0" * 8000)
            result = analyze_audio(good)
            self.assertEqual(result["duration_seconds"], 1.0)
            self.assertEqual(result["sample_rate_khz"], 8.0)
            self.assertEqual(result["bitrate_kbps"], 128.0)
            self.assertTrue(math.isfinite(result["loudness_dbfs"]))
            bad.write_bytes(b"broken")
            with self.assertRaises(AudioAnalysisError):
                analyze_audio(bad)


if __name__ == "__main__":
    unittest.main()
