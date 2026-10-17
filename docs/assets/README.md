# Safe documentation screenshot

`upload-empty.png` is an actual capture of the existing local synthetic-test upload page, not a design mockup or a detection result. A fresh browser context had no file, key, media, job, result, cookies or storage. API/job routes and external requests were blocked. Capture checks passed and the empty page was visually reviewed.

The image is 69,762 bytes. SHA256: `740cca8a9de0df8d6604a2832f87a23e1932ec2bd008af3321e332024dc00ea8`.

The original private report and PNG remain local. This exact approved copy is the sole image allowed in Git by `scripts/release_assets.py`. Changing its bytes or adding any other image fails the release gates. This exception does not allow bank frames, annotations, model results, keys or screenshots of private viewers.
