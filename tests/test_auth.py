import os
import json
from unittest import mock
from pr_sentinel.auth import get_token, set_token, load_config, get_github_token

@mock.patch('pr_sentinel.auth.CONFIG_FILE')
def test_set_and_load_token(mock_config_file, tmp_path):
    # Use a temporary file for config
    test_config = tmp_path / "config.json"
    mock_config_file.exists.return_value = True
    mock_config_file.open = test_config.open
    
    # Mock json reading/writing
    with mock.patch('pr_sentinel.auth.open', mock.mock_open(read_data="{}")) as m:
        set_token("github", "fake_token_123")
        m.assert_called_with(mock_config_file, "w")

@mock.patch.dict(os.environ, {"GITHUB_PAT": "env_token_456"})
def test_get_github_token_from_env():
    token = get_github_token()
    assert token == "env_token_456"
