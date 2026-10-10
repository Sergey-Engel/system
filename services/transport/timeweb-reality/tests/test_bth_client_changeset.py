import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import bth_client_changeset as changeset


class BthClientChangesetTests(unittest.TestCase):
    def test_transition_contract_accepts_only_reviewed_progression(self):
        wg_before = b"before-wg\n"
        allowed_before = b"before-allowed\n"
        wg_after = b"after-wg\n"
        allowed_after = b"after-allowed\n"
        old = {
            "image": "example",
            "hashes": {
                "wg": hashlib.sha256(wg_before).hexdigest(),
                "allowed": hashlib.sha256(allowed_before).hexdigest(),
            },
        }

        transition, final = changeset.transition_contract(
            copy.deepcopy(old), wg_before, allowed_before, wg_after, allowed_after
        )
        transition = json.loads(transition)
        final = json.loads(final)

        self.assertEqual(len(transition["wg_allowed_states"]), 3)
        self.assertEqual(transition["hashes"], old["hashes"])
        self.assertNotIn("wg_allowed_states", final)
        self.assertEqual(final["hashes"]["wg"], hashlib.sha256(wg_after).hexdigest())
        self.assertEqual(final["hashes"]["allowed"], hashlib.sha256(allowed_after).hexdigest())

    def test_transition_contract_rejects_incoherent_backup(self):
        with self.assertRaisesRegex(RuntimeError, "does not match"):
            changeset.transition_contract(
                {"hashes": {"wg": "0" * 64, "allowed": "0" * 64}},
                b"before-wg\n", b"before-allowed\n", b"after-wg\n", b"after-allowed\n"
            )

    def test_runtime_allowed_baseline_uses_wg_show_format(self):
        result = changeset.with_new_allowed(b"peer-a\t10.30.30.3/32 fd00:30:30::3/128\n", "peer-b")

        self.assertIn(b"peer-b\t10.30.30.6/32 fd00:30:30::6/128\n", result)

    def test_control_keeps_recovery_wg_baseline_in_lockstep(self):
        with tempfile.TemporaryDirectory() as directory:
            stage = Path(directory)
            values = {
                "wg.before": b"old-wg\n",
                "wg.after": b"new-wg\n",
                "recovery.before.sh": b"old-recovery\n",
                "recovery.after.sh": b"new-recovery\n",
                "recovery.wg.before": b"old-wg\n",
                "contract.before.json": b"old-contract\n",
                "contract.transition.json": b"transition-contract\n",
                "contract.after.json": b"new-contract\n",
                "allowed.before": b"old-allowed\n",
                "allowed.after": b"new-allowed\n",
                "peer.public": b"peer\n",
                "peer.psk": b"psk\n",
                "client.conf": b"client\n",
            }
            for name, value in values.items():
                (stage / name).write_bytes(value)

            control = changeset.control_script(stage).decode()
            expected = changeset.final_expected(stage)

        self.assertIn('need "$recovery/wg.baseline"', control)
        self.assertIn('install -m600 "$base/recovery.wg.before" "$recovery/wg.baseline"', control)
        self.assertIn('install -m600 "$base/wg.after" "$recovery/wg.baseline"', control)
        self.assertEqual(
            expected[changeset.RECOVERY + "/wg.baseline"],
            hashlib.sha256(b"new-wg\n").hexdigest(),
        )


if __name__ == "__main__":
    unittest.main()
