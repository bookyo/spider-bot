"""后台任务运行器测试。"""

import os
import signal
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api import task_runner


class TestTaskRunnerHelpers(unittest.TestCase):
    def test_describe_exit_code(self):
        self.assertEqual(
            task_runner.describe_process_exit(3),
            'exit_code=3',
        )

    def test_describe_signal_termination(self):
        description = task_runner.describe_process_exit(-signal.SIGKILL)
        self.assertIn('signal=SIGKILL', description)
        self.assertIn('signal_number=9', description)

    def test_build_log_path_uses_backend_runtime_logs(self):
        path = task_runner.build_backend_log_path(['incremental', '--limit', '5'])

        self.assertTrue(path.endswith('.log'))
        self.assertIn(os.path.join('backend', 'runtime_logs'), path)
        self.assertIn('incremental', os.path.basename(path))


if __name__ == '__main__':
    unittest.main()
