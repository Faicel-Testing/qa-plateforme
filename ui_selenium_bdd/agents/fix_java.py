import os, glob, re

dirs = [
    r"c:\Users\LENOVO\Desktop\QA_Plateforme\ui_selenium_bdd\src\test\java\com\qacart\todo\steps",
    r"c:\Users\LENOVO\Desktop\QA_Plateforme\ui_selenium_bdd\src\test\java\com\qacart\todo\pages"
]

fixed = 0
for d in dirs:
    for f in glob.glob(os.path.join(d, "*.java")):
        with open(f, encoding="utf-8", errors="replace") as fh:
            content = fh.read()
        lines = content.splitlines()
        cleaned_lines = [l for l in lines if not l.strip().startswith("```")]
        cleaned = "\n".join(cleaned_lines).strip()
        if cleaned != content.strip():
            with open(f, "w", encoding="utf-8") as fh:
                fh.write(cleaned + "\n")
            print(f"  fixed: {os.path.basename(f)}")
            fixed += 1
        else:
            print(f"  ok:    {os.path.basename(f)}")

print(f"\nTotal fixed: {fixed}")
