from unicodedata import normalize

def normalize_to_ascii(character):
    return normalize("NFD",character).encode("ASCII","ignore").decode("ASCII")

def yellow(string):
    return "\033[1;33m" + string + "\033[1;m"

def green(string):
    return "\033[1;32m" + string + "\033[1;m"

def red(string):
    return "\033[1;31m" + string + "\033[1;m"

def blue(string):
    return "\033[1;34m" + string + "\033[1;m"

def underline(string):
    return "\033[4m" + string + "\033[0m"