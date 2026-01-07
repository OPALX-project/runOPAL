import hashlib

"""
Simple path name generator that ensures that actual path lengths do not exceed
the UNIX 255 chars.

Directory names that are longer than 255 chars will be shortened to a sha
hash. The mapping can later be writte to stdout or file to have access to the
original filename.
"""
class PathNameGenerator:

    def __init__(self):

        self.mapping = {}
        self.max_path_length = 160


    def __str__(self):

        mapping = ""
        for hash_value, dir_name in self.mapping.items():
            mapping += hash_value + " => " + dir_name + "\n"

        return mapping


    def compress(self, path_name):

        if len(path_name) < self.max_path_length:
            return path_name

        h = hashlib.new('ripemd160')
        h.update(path_name.encode('utf-8'))
        path_name_hex = h.hexdigest()

        self.mapping[path_name_hex] = path_name

        return path_name_hex


