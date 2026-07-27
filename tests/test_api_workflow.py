import shutil
import subprocess
import tempfile
import time
import unittest
from pathlib import Path

from fastapi.testclient import TestClient

from vocallab.api import create_app


@unittest.skipUnless(shutil.which("ffmpeg") and shutil.which("ffprobe"), "FFmpeg unavailable")
class ApiWorkflowTests(unittest.TestCase):
    def _recording(self, path: Path, microphone_frequency: float) -> None:
        subprocess.run(
            [
                shutil.which("ffmpeg") or "ffmpeg",
                "-v",
                "error",
                "-f",
                "lavfi",
                "-i",
                f"sine=frequency={microphone_frequency}:duration=1.2:sample_rate=48000",
                "-f",
                "lavfi",
                "-i",
                "sine=frequency=440:duration=1.2:sample_rate=48000",
                "-map",
                "0:a",
                "-map",
                "1:a",
                "-metadata:s:a:0",
                "title=Microphone",
                "-metadata:s:a:1",
                "title=System Audio",
                "-c:a",
                "pcm_s16le",
                str(path),
            ],
            check=True,
        )

    def _analyze(self, client: TestClient, project_id: str, take_id: str) -> dict:
        response = client.post(
            f"/api/projects/{project_id}/takes/{take_id}/analyze",
            json={"separator": "fallback", "alignment_profile": "performance"},
        )
        self.assertEqual(response.status_code, 202)
        job_id = response.json()["job_id"]
        for _ in range(100):
            job = client.get(f"/api/jobs/{job_id}").json()
            if job["status"] in {"completed", "failed"}:
                self.assertEqual(job["status"], "completed", job.get("error"))
                return job
            time.sleep(0.05)
        self.fail("Analysis job did not finish.")

    def _import(
        self, client: TestClient, project_id: str, recording: Path
    ) -> str:
        inspected = client.post(
            f"/api/recordings/inspect?filename={recording.name}",
            content=recording.read_bytes(),
            headers={"content-type": "application/octet-stream"},
        )
        self.assertEqual(inspected.status_code, 200, inspected.text)
        payload = inspected.json()
        self.assertEqual(len(payload["streams"]), 2)
        self.assertTrue(payload["streams"][0]["preview_url"])
        response = client.post(
            f"/api/projects/{project_id}/takes",
            json={
                "recording_token": payload["token"],
                "microphone_stream": payload["streams"][0]["index"],
                "reference_stream": payload["streams"][1]["index"],
            },
        )
        self.assertEqual(response.status_code, 201, response.text)
        return response.json()["take_id"]

    def test_complete_ui_facing_two_take_workflow(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with TestClient(create_app(root / "library")) as client:
                capability = client.get("/api/capabilities").json()["demucs"]
                self.assertEqual(capability["model"], "htdemucs")
                self.assertFalse(capability["automatic_download"])
                created = client.post(
                    "/api/projects",
                    json={"title": "Synthetic", "artist": "Fixture"},
                )
                self.assertEqual(created.status_code, 201)
                project_id = created.json()["id"]
                self.assertEqual(len(client.get("/api/projects").json()), 1)
                read = client.get(f"/api/projects/{project_id}")
                self.assertEqual(read.status_code, 200)
                invalid_assignment = client.post(
                    f"/api/projects/{project_id}/takes",
                    json={
                        "recording_token": "0" * 32,
                        "microphone_stream": 0,
                        "reference_stream": 0,
                    },
                )
                self.assertEqual(invalid_assignment.status_code, 400)

                first_recording = root / "first.mkv"
                self._recording(first_recording, 466.16)
                first_take = self._import(client, project_id, first_recording)
                first_job = self._analyze(client, project_id, first_take)
                self.assertFalse(first_job["result"]["baseline_reused"])

                take_payload = client.get(
                    f"/api/projects/{project_id}/takes/{first_take}"
                ).json()
                self.assertEqual(
                    take_payload["analysis"]["transposition"]["best_shift"], 1
                )
                view = client.get(
                    f"/api/projects/{project_id}/takes/{first_take}/visualization"
                )
                self.assertEqual(view.status_code, 200, view.text)
                self.assertTrue(view.json()["pitch"]["time"])
                self.assertTrue(
                    view.json()["transport"]["mapping"]["canonical_time"]
                )
                self.assertIn("practice_targets", view.json())
                before_scoring = take_payload["analysis"]
                manual_scoring = client.get(
                    f"/api/projects/{project_id}/takes/{first_take}/scoring",
                    params={"shift": 0},
                )
                self.assertEqual(manual_scoring.status_code, 200, manual_scoring.text)
                self.assertEqual(
                    manual_scoring.json()["scoring"]["shift_source"], "manual"
                )
                self.assertEqual(
                    manual_scoring.json()["scoring"]["selected_shift"], 0
                )
                self.assertIn("practice_targets", manual_scoring.json())
                after_scoring = client.get(
                    f"/api/projects/{project_id}/takes/{first_take}"
                ).json()["analysis"]
                self.assertEqual(before_scoring, after_scoring)
                saved_offset = client.put(
                    f"/api/projects/{project_id}/takes/{first_take}/playback-offset",
                    json={"offset_seconds": 0.61},
                )
                self.assertEqual(saved_offset.status_code, 200)
                self.assertAlmostEqual(
                    client.get(
                        f"/api/projects/{project_id}/takes/{first_take}"
                    ).json()["playback_offset_seconds"],
                    0.61,
                )
                audio = client.get(
                    f"/api/projects/{project_id}/takes/{first_take}/audio/user"
                )
                self.assertEqual(audio.status_code, 200)
                self.assertEqual(
                    client.get(
                        f"/api/projects/{project_id}/takes/{first_take}/audio/secret"
                    ).status_code,
                    404,
                )

                baseline = client.get(f"/api/projects/{project_id}/baseline").json()
                notes = baseline["notes"]
                self.assertTrue(baseline["versions"][0]["pitch_preview"]["time"])
                self.assertEqual(
                    baseline["versions"][0]["engine"], "reference-mix-fallback-v1"
                )
                notes[0]["midi_pitch"] += 1
                version = client.post(
                    f"/api/projects/{project_id}/baseline/versions",
                    json={"take_id": first_take, "notes": notes},
                )
                self.assertEqual(version.status_code, 201, version.text)
                self.assertEqual(version.json()["version"], 2)
                versions = client.get(f"/api/projects/{project_id}/baseline").json()[
                    "versions"
                ]
                activated = client.post(
                    f"/api/projects/{project_id}/baseline/{versions[0]['id']}/activate"
                )
                self.assertEqual(activated.json()["version"], 1)
                client.post(
                    f"/api/projects/{project_id}/baseline/{versions[1]['id']}/activate"
                )
                rerun = self._analyze(client, project_id, first_take)
                stages = rerun["details"]
                self.assertEqual(
                    stages["reference_preparation"]["baseline_version"], 2
                )
                cache_events = stages["pitch_tracking"]["cache_events"]
                self.assertIn(
                    {"stage": "extract-microphone", "status": "hit"}, cache_events
                )
                self.assertIn(
                    {"stage": "extract-reference", "status": "hit"}, cache_events
                )
                self.assertIn({"stage": "pitch-user", "status": "hit"}, cache_events)
                self.assertNotIn(
                    {"stage": "separate", "status": "miss"}, cache_events
                )

                second_recording = root / "second.mkv"
                self._recording(second_recording, 440)
                second_take = self._import(client, project_id, second_recording)
                second_job = self._analyze(client, project_id, second_take)
                self.assertTrue(second_job["result"]["baseline_reused"])
                comparison = client.get(
                    f"/api/projects/{project_id}/compare",
                    params={"first": first_take, "second": second_take},
                )
                self.assertEqual(comparison.status_code, 200, comparison.text)
                self.assertEqual(comparison.json()["second_take_id"], second_take)
                self.assertEqual(
                    comparison.json()["metrics_mode"], "transposition_adjusted"
                )
                self.assertTrue(comparison.json()["contours"]["first"]["time"])

                disposable = client.post(
                    "/api/projects",
                    json={"title": "Delete Me", "artist": "Fixture"},
                ).json()
                refused = client.request(
                    "DELETE",
                    f"/api/projects/{disposable['id']}",
                    json={"confirmation": "wrong"},
                )
                self.assertEqual(refused.status_code, 400)
                deleted = client.request(
                    "DELETE",
                    f"/api/projects/{disposable['id']}",
                    json={"confirmation": "Delete Me"},
                )
                self.assertEqual(deleted.status_code, 200)


if __name__ == "__main__":
    unittest.main()
