import os
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from internal import release


class TestGiteaRepoInfo(unittest.TestCase):
    def test_ssh_url_with_port(self):
        info = release.get_gitea_repo_info(
            "ssh://git@dev.senseglove.com:3181/R1/r1_api_dev.git"
        )
        self.assertEqual(info, ("R1", "r1_api_dev", "https://dev.senseglove.com"))

    def test_ssh_at_url(self):
        info = release.get_gitea_repo_info("git@dev.senseglove.com:R1/r1_api_dev.git")
        self.assertEqual(info, ("R1", "r1_api_dev", "https://dev.senseglove.com"))

    def test_https_url(self):
        info = release.get_gitea_repo_info(
            "https://dev.senseglove.com/R1/r1_api_dev.git"
        )
        self.assertEqual(info, ("R1", "r1_api_dev", "https://dev.senseglove.com"))

    def test_gitlab_url_returns_none(self):
        self.assertIsNone(
            release.get_gitea_repo_info(
                "git@gitlab.com:senseglove/rembrandt/rembrandt-api.git"
            )
        )

    def test_github_url_returns_none(self):
        self.assertIsNone(
            release.get_gitea_repo_info("git@github.com:Adjuvo/SenseGlove-R1-API.git")
        )


class TestCreateGiteaRelease(unittest.TestCase):
    def test_dry_run_does_not_call_api(self):
        with patch("urllib.request.urlopen") as mock_urlopen:
            result = release.create_gitea_release(
                "R1",
                "r1_api_dev",
                "Release/v0.0.99",
                "Test release notes",
                dry_run=True,
            )
        self.assertTrue(result)
        mock_urlopen.assert_not_called()

    def test_missing_token_skips_api_call(self):
        with patch.dict(os.environ, {}, clear=True):
            with patch("internal.release.get_gitea_token", return_value=None):
                with patch("urllib.request.urlopen") as mock_urlopen:
                    result = release.create_gitea_release(
                        "R1",
                        "r1_api_dev",
                        "Release/v0.0.99",
                        "Test release notes",
                    )
        self.assertTrue(result)
        mock_urlopen.assert_not_called()

    def test_existing_release_skips_create(self):
        with patch(
            "internal.release.check_gitea_release_exists", return_value=True
        ) as mock_exists:
            with patch("urllib.request.urlopen") as mock_urlopen:
                result = release.create_gitea_release(
                    "R1",
                    "r1_api_dev",
                    "Release/v0.0.99",
                    "Test release notes",
                    gitea_token="test-token",
                )
        self.assertTrue(result)
        mock_exists.assert_called_once()
        mock_urlopen.assert_not_called()


if __name__ == "__main__":
    unittest.main()
