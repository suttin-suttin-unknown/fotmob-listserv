#!/bin/bash

function remove_pycache_files() {
    find "$1" -type f -name "*.pyc" -delete
}

function remove_pycache_directories() {
    find "$1" -type d -name "__pycache__" -exec rm -r {} +
}

current_dir=$(pwd)
remove_pycache_files "$current_dir"
remove_pycache_directories "$current_dir"
