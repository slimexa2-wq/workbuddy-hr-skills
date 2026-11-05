import unittest
import os
import tempfile
import json
import logging
from unittest.mock import patch, MagicMock

import psutil

# Import the module under test
import ultra_modules.orphan_agent_process_reaper_cli_one_click as reaper_module

class TestOrphanAgentProcessReaper(unittest.TestCase):

    def setUp(self):
        # Create a temporary directory for output files
        self.temp_dir = tempfile.TemporaryDirectory()
        self.output_dir = self.temp_dir.name

    def tearDown(self):
        # Clean up temporary directory
        self.temp_dir.cleanup()

    def test_init_dirty_data_self_healing(self):
        """Test that OrphanProcessReaper handles missing/dirty parameters with default fallbacks."""
        # 1. Default parameters
        reaper = reaper_module.OrphanProcessReaper()
        self.assertEqual(reaper.target_keywords, reaper_module.OrphanProcessReaper.DEFAULT_TARGET_KEYWORDS)
        self.assertFalse(reaper.dry_run)

        # 2. Dirty parameters (None, empty list, invalid types)
        reaper = reaper_module.OrphanProcessReaper(target_keywords=None)
        self.assertEqual(reaper.target_keywords, reaper_module.OrphanProcessReaper.DEFAULT_TARGET_KEYWORDS)

        reaper = reaper_module.OrphanProcessReaper(target_keywords=[])
        self.assertEqual(reaper.target_keywords, reaper_module.OrphanProcessReaper.DEFAULT_TARGET_KEYWORDS)

        reaper = reaper_module.OrphanProcessReaper(target_keywords=["Chrome", "", None, 123])
        self.assertEqual(reaper.target_keywords, ["chrome", "123"])

        reaper = reaper_module.OrphanProcessReaper(dry_run="Yes")
        self.assertTrue(reaper.dry_run)

    @patch('psutil.process_iter')
    def test_reap_normal_operation(self, mock_process_iter):
        """Test normal reap operation identifying and terminating processes."""

        # Mocking process 1: An orphaned target process
        proc1 = MagicMock()
        proc1.info = {
            'pid': 1001,
            'name': 'chrome',
            'ppid': 1,
            'cmdline': ['chrome', '--headless'],
            'memory_info': MagicMock(rss=104857600) # 100 MB
        }
        proc1.ppid.return_value = 1
        proc1.name.return_value = 'chrome'
        proc1.cmdline.return_value = ['chrome', '--headless']

        # Mocking process 2: A non-orphaned target process (ppid != 1)
        proc2 = MagicMock()
        proc2.info = {
            'pid': 1002,
            'name': 'chrome',
            'ppid': 1000,
            'cmdline': ['chrome'],
            'memory_info': MagicMock(rss=50000000)
        }
        proc2.ppid.return_value = 1000
        proc2.name.return_value = 'chrome'
        proc2.cmdline.return_value = ['chrome']

        # Mocking process 3: An orphaned non-target process
        proc3 = MagicMock()
        proc3.info = {
            'pid': 1003,
            'name': 'bash',
            'ppid': 1,
            'cmdline': ['bash'],
            'memory_info': MagicMock(rss=10000000)
        }
        proc3.ppid.return_value = 1
        proc3.name.return_value = 'bash'
        proc3.cmdline.return_value = ['bash']

        mock_process_iter.return_value = [proc1, proc2, proc3]

        reaper = reaper_module.OrphanProcessReaper()
        report = reaper.reap()

        self.assertEqual(report['total_processes_identified'], 1)
        self.assertEqual(report['total_memory_freed_mb'], 100.0)
        self.assertEqual(len(report['processes']), 1)
        self.assertEqual(report['processes'][0]['pid'], 1001)
        self.assertEqual(report['processes'][0]['status'], 'terminated')
        proc1.terminate.assert_called_once()
        proc2.terminate.assert_not_called()
        proc3.terminate.assert_not_called()

    @patch('psutil.process_iter')
    def test_reap_exceptions_and_dry_run(self, mock_process_iter):
        """Test boundary conditions, psutil exceptions, and dry-run mode."""
        proc1 = MagicMock()
        proc1.info = {
            'pid': 2001,
            'name': 'node',
            'ppid': 1,
            'cmdline': ['node', 'server.js'],
            'memory_info': None # Missing memory info
        }
        proc1.ppid.return_value = 1
        proc1.name.return_value = 'node'
        proc1.cmdline.return_value = ['node', 'server.js']
        proc1.terminate.side_effect = psutil.AccessDenied(pid=2001)

        proc2 = MagicMock()
        proc2.info = {
            'pid': 2002,
            'name': 'playwright',
            'ppid': 1,
            'cmdline': ['playwright'],
            'memory_info': MagicMock(rss=10485760) # 10 MB
        }
        proc2.ppid.return_value = 1
        proc2.name.return_value = 'playwright'
        proc2.cmdline.return_value = ['playwright']
        proc2.terminate.side_effect = psutil.NoSuchProcess(pid=2002)

        proc3 = MagicMock()
        proc3.info = {
            'pid': 2003,
            'name': 'mcp',
            'ppid': 1,
            'cmdline': [], # Empty cmdline fallback
            'memory_info': MagicMock(rss=20971520) # 20 MB
        }
        proc3.ppid.return_value = 1
        proc3.name.return_value = 'mcp'
        proc3.cmdline.side_effect = psutil.AccessDenied(pid=2003)
        proc3.terminate.side_effect = Exception("Generic Error")

        # Test ZombieProcess during cmdline
        proc4 = MagicMock()
        proc4.info = {'pid': 2004, 'name': 'agent', 'ppid': 1}
        proc4.ppid.return_value = 1
        proc4.name.return_value = 'agent'
        proc4.cmdline.side_effect = psutil.ZombieProcess(pid=2004)

        # Process raising error during is_target_process
        proc5 = MagicMock()
        proc5.ppid.side_effect = psutil.NoSuchProcess(pid=2005)

        mock_process_iter.return_value = [proc1, proc2, proc3, proc4, proc5]

        reaper = reaper_module.OrphanProcessReaper()
        report = reaper.reap()

        self.assertEqual(report['total_processes_identified'], 4)

        statuses = [p['status'] for p in report['processes']]
        self.assertIn('access_denied', statuses)
        self.assertIn('already_dead', statuses)
        self.assertIn('error_Generic Error', statuses)

        # Test dry-run
        reaper_dry = reaper_module.OrphanProcessReaper(dry_run=True)
        report_dry = reaper_dry.reap()
        self.assertEqual(report_dry['total_processes_identified'], 4)
        self.assertTrue(all(p['status'] == 'identified' for p in report_dry['processes']))

    def test_export_to_json_edge_cases(self):
        """Test JSON export with dirty inputs and file IO errors."""
        report = {"test": "data"}

        # Normal
        json_path = os.path.join(self.output_dir, "test.json")
        self.assertTrue(reaper_module.export_to_json(report, json_path))
        self.assertTrue(os.path.exists(json_path))

        # Dirty filepath (None, int) -> fallback to default
        with patch('builtins.open', unittest.mock.mock_open()) as mocked_open:
            self.assertTrue(reaper_module.export_to_json(report, None))
            mocked_open.assert_called_with("reaper_report.json", 'w', encoding='utf-8')

            self.assertTrue(reaper_module.export_to_json(report, 123))
            mocked_open.assert_called_with("reaper_report.json", 'w', encoding='utf-8')

        # File IO Error
        with patch('builtins.open', side_effect=PermissionError("Denied")):
            self.assertFalse(reaper_module.export_to_json(report, json_path))

    @patch('ultra_modules.orphan_agent_process_reaper_cli_one_click.HAS_OPENPYXL', True)
    def test_export_to_excel_edge_cases(self):
        """Test Excel export with dirty inputs, missing data, and errors."""
        report = {
            "timestamp": "2023-10-27T10:00:00",
            "dry_run": False,
            "total_processes_identified": 1,
            "total_memory_freed_mb": 10.5,
            "processes": [{"pid": 1, "name": "node", "memory_mb": 10.5, "status": "terminated", "cmdline": "node"}]
        }

        excel_path = os.path.join(self.output_dir, "test.xlsx")
        self.assertTrue(reaper_module.export_to_excel(report, excel_path))
        self.assertTrue(os.path.exists(excel_path))

        # Dirty filepath fallback
        with patch('openpyxl.Workbook') as mock_wb:
            mock_instance = mock_wb.return_value
            self.assertTrue(reaper_module.export_to_excel(report, None))
            mock_instance.save.assert_called_with("reaper_report.xlsx")

        # Empty report robustness
        self.assertTrue(reaper_module.export_to_excel({}, excel_path))

        # Exception during save
        with patch('openpyxl.Workbook') as mock_wb:
            mock_instance = mock_wb.return_value
            mock_instance.save.side_effect = IOError("Disk full")
            self.assertFalse(reaper_module.export_to_excel(report, excel_path))

    @patch('ultra_modules.orphan_agent_process_reaper_cli_one_click.HAS_OPENPYXL', False)
    def test_export_to_excel_no_openpyxl(self):
        self.assertFalse(reaper_module.export_to_excel({}, "test.xlsx"))

    @patch('ultra_modules.orphan_agent_process_reaper_cli_one_click.OrphanProcessReaper')
    def test_run_reaper_cli_one_click(self, mock_reaper_class):
        """Test one-click CLI with zero-configuration and dirty inputs."""
        mock_instance = mock_reaper_class.return_value
        mock_instance.reap.return_value = {"status": "ok"}

        # 1. Zero config
        results = reaper_module.run_reaper_cli()
        self.assertEqual(results['report'], {"status": "ok"})
        self.assertIn('json', results['exports'])
        self.assertIn('excel', results['exports'])

        # 2. Dirty export_formats
        results = reaper_module.run_reaper_cli(export_formats="InvalidType")
        self.assertIn('json', results['exports'])

        results = reaper_module.run_reaper_cli(export_formats=["", None])
        self.assertIn('json', results['exports'])

        # 3. Custom output_dir and dirty output_dir
        results = reaper_module.run_reaper_cli(output_dir=self.output_dir)
        self.assertTrue(results['exports']['json']['path'].startswith(self.output_dir))

        results = reaper_module.run_reaper_cli(output_dir=123)
        self.assertTrue(results['exports']['json']['path'].startswith("."))

        # 4. output_dir os.makedirs exception fallback
        with patch('os.makedirs', side_effect=PermissionError):
            results = reaper_module.run_reaper_cli(output_dir="/root/forbidden")
            self.assertTrue(results['exports']['json']['path'].startswith("."))

    def test_import_error(self):
        import sys
        import importlib
        with patch.dict(sys.modules, {'openpyxl': None}):
            import ultra_modules.orphan_agent_process_reaper_cli_one_click as mod
            importlib.reload(mod)
            self.assertFalse(mod.HAS_OPENPYXL)

        # Restore module
        importlib.reload(reaper_module)

    @patch('ultra_modules.orphan_agent_process_reaper_cli_one_click.OrphanProcessReaper')
    def test_run_reaper_cli_empty_formats_and_main(self, mock_reaper_class):
        mock_instance = mock_reaper_class.return_value
        mock_instance.reap.return_value = {"total_memory_freed_mb": 0}

        # Empty list formats
        results = reaper_module.run_reaper_cli(export_formats=[])
        self.assertIn('json', results['exports'])
        self.assertIn('excel', results['exports'])

        # Test missing formats in list branch
        results = reaper_module.run_reaper_cli(export_formats=["none"])
        self.assertNotIn('json', results['exports'])
        self.assertNotIn('excel', results['exports'])

    def test_main_block(self):
        with patch('ultra_modules.orphan_agent_process_reaper_cli_one_click.run_reaper_cli') as mock_run:
            mock_run.return_value = {
                'report': {'total_memory_freed_mb': 100},
                'exports': {}
            }
            # Execute main block logic
            with patch('builtins.print'):
                import runpy
                runpy.run_path('ultra_modules/orphan_agent_process_reaper_cli_one_click.py', run_name='__main__')

if __name__ == '__main__':
    unittest.main()
