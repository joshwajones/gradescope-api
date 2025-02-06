"""Basic utilities for using Python requests to interact with Gradescope."""

from __future__ import annotations

import io
import logging
import zipfile
from pathlib import Path
from typing import TYPE_CHECKING

import requests
from bs4 import BeautifulSoup
from tqdm import tqdm

if TYPE_CHECKING:
    from pyscope.course import GSCourse


def get_csrf_token(course: GSCourse) -> str:
    """Get the CSRF token for a GradeScope course."""
    membership_resp = course.session.get(f"{course.url}/memberships")
    parsed_membership_resp = BeautifulSoup(membership_resp.text, "html.parser")
    return parsed_membership_resp.find("meta", attrs={"name": "csrf-token"}).get(
        "content",
    )


def _byte_to_mb(num_bytes: int) -> float:
    return float(num_bytes) / (1024 * 1024)


def stream_file(
    session: requests.Session,
    url: str,
    write_to: Path | str,
    chunk_size: int = 8192,
    unzip: bool = True,
    show_bar: bool = True,
) -> None:
    """Streams a ZIP file from a URL and extracts its contents.

    Args:
        session (requests.Session): The requests session to use for the download.
        url (str): The URL of the ZIP file to download.
        write_to (str or Path): The directory to extract the contents to.
        chunk_size (int): The size of each chunk to download.
        unzip (bool): Whether to unzip the file after downloading.
        show_bar (bool): Whether to show a progress bar.

    """
    write_to = Path(write_to)
    with session.get(url, stream=True) as response:
        total_size = int(response.headers.get("content-length", 0))

        with (
            io.BytesIO() as file_stream,
            tqdm(
                desc="Downloading zip file...",
                total=total_size,
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
                disable=not show_bar,
            ) as bar,
        ):
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    file_stream.write(chunk)
                    bar.update(len(chunk))

            logging.debug(
                "Successfully downloaded %.2f MB",
                _byte_to_mb(file_stream.getbuffer().nbytes),
            )
            file_stream.seek(0)
            if unzip:
                with zipfile.ZipFile(file_stream) as zip_file:
                    zip_file.extractall(write_to)
                    logging.debug("Files extracted successfully to %s", write_to)
            else:
                with write_to.open("wb") as file:
                    file.write(file_stream.read())
                logging.debug("File successfull written to: %s", write_to)


class SafeSession(requests.Session):
    """A thin wrapper around requests.Session that by default checks for errors, and dumps some debug info."""

    def request(self, method: str, url: str, *args, _raise: bool = True, **kwargs) -> requests.Response:  # noqa: ANN002, ANN003, D102
        response = super().request(method, url, **kwargs)
        if _raise:
            try:
                response.raise_for_status()
            except requests.exceptions.HTTPError:
                logging.exception(
                    "Attempted to request %s on %s with args %s and kwargs %s.\nStatus code: %d",
                    method,
                    url,
                    args,
                    kwargs,
                    response.status_code,
                )
                raise
        return response
