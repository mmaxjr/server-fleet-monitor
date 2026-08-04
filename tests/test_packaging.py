import tomllib
from pathlib import Path


def test_hatch_build_includes_import_package():
    pyproject = tomllib.loads(Path("pyproject.toml").read_text(encoding="utf-8"))

    wheel_config = pyproject["tool"]["hatch"]["build"]["targets"]["wheel"]

    assert wheel_config["packages"] == ["fleet_monitor"]
