# download_audiobook
Input a URL to a webpage that hosts listening online to an audiobook and scrape the audio files to listen offline

There are many websites that host old audiobooks where you can listen to them through the webpage. This script scrapes the audio files, allowing you to move them to an audiobook player of your choice.



# Usage
Download all audio from a webpage.

"python ./download_audiobook.py </URL> <FILE_NAME_PREFIX>"

positional arguments:
  url                   URL of the webpage to scrape
  prefix                Prefix for all file names

options:
  -h, --help            show this help message and exit
  -d DIRECTORY, --directory DIRECTORY
                        Directory to put the downloaded files

