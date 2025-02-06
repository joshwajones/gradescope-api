from __future__ import annotations
import requests
import zipfile
import io
from tqdm import tqdm
import logging
from bs4 import BeautifulSoup
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pyscope.course import GSCourse


class DummyBar:
    """Dummy progress bar for when tqdm is not available or user has disabled it"""

    def __init__(self, *args, **kwargs):
        pass

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        pass

    def update(self, *args, **kwargs):
        pass


def get_csrf_token(course: GSCourse) -> str:
    membership_resp = course.session.get(f"{course.url}/memberships")
    parsed_membership_resp = BeautifulSoup(membership_resp.text, "html.parser")
    authenticity_token = parsed_membership_resp.find("meta", attrs={"name": "csrf-token"}).get(
        "content"
    )
    return authenticity_token


def byte_to_mb(bytes: int) -> float:
    return float(bytes) / (1024 * 1024)


def stream_file(
    session: requests.Session,
    url: str,
    write_to: str,
    chunk_size: int = 8192,
    unzip: bool = True,
    show_bar: bool = True,
) -> None:
    """
    Streams a ZIP file from a URL and extracts its contents.

    Args:
        session (requests.Session): The requests session to use for the download.
        url (str): The URL of the ZIP file to download.
        extract_to (str): The directory to extract the contents to.
        chunk_size (int): The size of each chunk to download.
        unzip (bool): Whether to unzip the file after downloading.
        show_bar (bool): Whether to show a progress bar.
    """
    bar_constructor = DummyBar if not show_bar else tqdm
    with session.get(url, stream=True) as response:
        total_size = int(response.headers.get("content-length", 0))

        with (
            io.BytesIO() as file_stream,
            bar_constructor(
                desc="Downloading zip file...",
                total=total_size,
                unit="B",
                unit_scale=True,
                unit_divisor=1024,
            ) as bar,
        ):
            for chunk in response.iter_content(chunk_size=chunk_size):
                if chunk:
                    file_stream.write(chunk)
                    bar.update(len(chunk))

            logging.debug(
                f"Successfully downloaded {byte_to_mb(file_stream.getbuffer().nbytes)} MB"
            )
            file_stream.seek(0)
            if unzip:
                with zipfile.ZipFile(file_stream) as zip_file:
                    zip_file.extractall(write_to)
                    logging.debug(f"Files extracted successfully to {write_to}")
            else:
                with open(write_to, "wb") as file:
                    file.write(file_stream.read())
                logging.debug(f"File successfull written to: {write_to}")


class SafeSession(requests.Session):
    """
    A thin wrapper around requests.Session that by default checks for errors, and dumps some debug info
    """

    def request(self, method, url, *args, _raise=True, **kwargs):
        response = super().request(method, url, **kwargs)
        if _raise:
            try:
                response.raise_for_status()
            except requests.exceptions.HTTPError as e:
                logging.debug(
                    f"Attempted to request {method} on {url} with args {args} and kwargs {kwargs}.\nStatus code: {response.status_code}"
                )
                logging.debug(f"Error: {e}")
                raise e
        return response
