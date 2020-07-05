import setuptools

with open("README.md", "r") as fh:
    long_description = fh.read()

setuptools.setup(
    name="pyxair",
    version="0.0.2",
    author="Shad Sharma",
    author_email="shadanan@gmail.com",
    description="A library for interacting with Behringer XAir devices.",
    long_description=long_description,
    long_description_content_type="text/markdown",
    url="https://github.com/shadanan/pyxair",
    packages=["pyxair"],
    install_requires=["python-osc"],
    classifiers=[
        "Development Status :: 2 - Pre-Alpha",
        "Programming Language :: Python :: 3",
        "License :: OSI Approved :: MIT License",
        "Operating System :: OS Independent",
    ],
    python_requires=">=3.7",
)
