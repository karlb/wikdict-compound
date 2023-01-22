from setuptools import setup
import os

VERSION = "0.2"


def get_long_description():
    with open(
        os.path.join(os.path.dirname(os.path.abspath(__file__)), "README.md"),
        encoding="utf8",
    ) as fp:
        return fp.read()


setup(
    name="wikdict-compound",
    description="Compound word splitter, dictionary-based",
    long_description=get_long_description(),
    long_description_content_type="text/markdown",
    author="Karl Bartel",
    url="https://github.com/karlb/wikdict-compound",
    project_urls={
        "Issues": "https://github.com/karlb/wikdict-compound/issues",
        "CI": "https://github.com/karlb/wikdict-compound/actions",
        "Changelog": "https://github.com/karlb/wikdict-compound/releases",
    },
    version=VERSION,
    packages=["wikdict_compound"],
    install_requires=[],
    extras_require={"test": ["pytest"]},
    python_requires=">=3.9",
)
