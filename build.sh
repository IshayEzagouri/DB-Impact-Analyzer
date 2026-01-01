#!/bin/bash
if [ -f "lambda-package.zip" ]; then
    rm lambda-package.zip
fi
if [ -d "build" ]; then
    rm -rf build
fi
mkdir build
pip install -r requirements.txt -t build/ --platform manylinux2014_x86_64 --only-binary=:all:
cp -r src build/
cd build/
zip -r ../lambda-package.zip .
cd ..
rm -rf build