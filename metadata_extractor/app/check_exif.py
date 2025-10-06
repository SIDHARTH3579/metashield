import exifread

file_path = "C:\\path\\to\\your\\photo.jpg"   # <-- change this to your image path

with open(file_path, "rb") as f:
    tags = exifread.process_file(f, details=True)

for tag in tags.keys():
    print(f"{tag}: {tags[tag]}")
