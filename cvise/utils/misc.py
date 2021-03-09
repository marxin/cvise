def is_readable_file(filename):
    try:
        open(filename).read()
        return True
    except UnicodeDecodeError:
        return False
