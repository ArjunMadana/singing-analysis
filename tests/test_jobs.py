import threading
import unittest

from vocallab.jobs import JobManager


class JobManagerTests(unittest.TestCase):
    def test_records_progress_and_completion(self) -> None:
        manager = JobManager(workers=1)
        finished = threading.Event()

        def work(progress):
            progress("pitch_tracking", "running", None)
            progress("pitch_tracking", "completed", {"tracker": "test"})
            finished.set()
            return {"take_id": "take", "baseline_reused": True}

        job = manager.submit("project", "take", work)
        self.assertTrue(finished.wait(2))
        current = manager.get(job.id)
        self.assertIsNotNone(current)
        self.assertEqual(current.status, "completed")
        self.assertEqual(current.stages["pitch_tracking"], "completed")


if __name__ == "__main__":
    unittest.main()
