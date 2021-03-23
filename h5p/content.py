from django.conf import settings
import tempfile
import shutil
import zipfile
import json
import os
from pathlib import Path
from .models import (
    H5PContent,
    H5PLibrary,
)


H5P_DIR = settings.MEDIA_ROOT  / "h5p"
CONTENT_DIR = H5P_DIR / "content"
LIBRARY_DIR = H5P_DIR / "libraries"
if not H5P_DIR.exists():
    H5P_DIR.mkdir(parents=True, exist_ok=True)
if not CONTENT_DIR.exists():
    CONTENT_DIR.mkdir(parents=True, exist_ok=True)
if not LIBRARY_DIR.exists():
    LIBRARY_DIR.mkdir(parents=True, exist_ok=True)


def get_library_path(library):
    return LIBRARY_DIR / library.machine_name


def get_library_json(library):
    json_path = get_library_path(library) / "library.json"
    ld_file = open(json_path)
    ld_json = json.load(ld_file)
    ld_file.close()
    return ld_json


def get_subdirectories(d):
    return filter(os.path.isdir, [os.path.join(d, f) for f in os.listdir(d)])


def process_library(ld):
    ld_file = open(Path(ld) / "library.json", "r")
    ld_json = json.load(ld_file)
    ld_file.close()
    # TODO inspect library json, compare to existing library objects
    # if its not in there create a new library object
    # libraries are stored in upload/h5p/libraries/name
    library, created = H5PLibrary.objects.get_or_create(
        machine_name=ld_json["machineName"],
        major_version=ld_json["majorVersion"],
        minor_version=ld_json["minorVersion"],
        patch_version=ld_json["patchVersion"],
        title=ld_json["title"]
    )
    if created:
        for key in [
                ("preloadedJs", "preloaded_js"),
                ("preloadedCss", "preloaded_css"),
                ("fullscreen", "fullscreen"),
                ("runnable", "runnable")
        ]:
            json_name = key[0]
            db_name = key[1]
            if json_name in ld_json:
                setattr(library, db_name, ld_json[json_name])
        # check for semantics file
        semantics_path = Path(ld) / "semantics.json"
        if semantics_path.exists():
            with open(semantics_path, "r") as semantics_file:
                semantics_json = json.load(semantics_file)
                library.semantics = json.dumps(semantics_json)
        library.save()
        library.json = ld_json
        library_path = f"{library.machine_name}-{library.major_version}.{library.minor_version}"
        Path(ld).rename(LIBRARY_DIR / library_path)
        print(LIBRARY_DIR / library_path)
    else:
        print("Process Library="+ld)
        print(ld_json)
    return library


def process_library_dependencies(library):
    lib_json = get_library_json(library)
    content_libraries = [library]
    # TODO add library dependencies
    if "preloadedDependencies" in lib_json:
        for preload in lib_json["preloadedDependencies"]:
            required_library = H5PLibrary.objects.get(machine_name=preload["machineName"])
            dependency, created = H5PLibraryDependency.objects.get_or_create(library=library, required_library=required_library, dependency_type="preloaded")
            if required_library not in content_libraries:
                content_libraries.append(required_library)
    editor_libraries = []
    if "editorDependencies" in lib_json:
        for editor_dep in lib_json["editorDependencies"]:
            required_library = H5PLibrary.objects.get(machine_name=editor_dep["machineName"])
            dependency, created = H5PLibraryDependency.objects.get_or_create(library=library, required_library=required_library, dependency_type="editor")
    return {"content_libraries": content_libraries, "editor_libraries": editor_libraries}


def h5p_file_process(h5p_file, content_name=""):

    tmpdir = Path(tempfile.mkdtemp())
    #try:
    file_path = h5p_file.h5p_file.file.name
    print(file_path)
    if 1 == 1:
        is_zipfile = zipfile.is_zipfile(file_path)
        print(is_zipfile)
        if is_zipfile:
            with zipfile.ZipFile(file_path) as libzip:
                libzip.extractall(tmpdir)
        #print(glob.glob(tmpdir+"/*"))
        h5p_file_path = tmpdir / "h5p.json"
        
        if h5p_file_path.is_file():
            h5p_file = open(h5p_file_path)
            h5p_json = json.load(h5p_file)
            subdirs = get_subdirectories(tmpdir)
            libdirs = []
            for sd in subdirs:
                subdir_lib_path = Path(sd) / "library.json"
                if subdir_lib_path.is_file():
                    libdirs.append(sd)
            libraries = []
            for ld in libdirs:
                library = process_library(ld)
                libraries.append(library)
            content_path = tmpdir / "content"
            print("CONTENT PATH=" + str(content_path))
            if content_path.exists():
                print("Content Path Exists")
                content_json_path = content_path / "content.json"
                print("Content Json=" + str(content_json_path))
                if content_json_path.is_file():
                    print("JSON Path is File")
                    content_file = open(content_json_path, "r")
                    content_json = json.load(content_file)
                    main_library = H5PLibrary.objects.get(machine_name=h5p_json["mainLibrary"])
                    content = H5PContent.objects.create(json_content=json.dumps(content_json), main_library=main_library, name=content_name)

                    for key in [("embedTypes", "embed_types"), ("contentType", "content_type"), ("author", "author"), ("license", "license"), ("metaKeywords", "meta_keywords"), ("metaDescription", "meta_description"), ("filtered", "filtered"), ("slug", "slug")]:
                        json_name = key[0]
                        db_name = key[1]
                        if json_name in h5p_json:
                            setattr(content, db_name, h5p_json[json_name])
                    content.save()
                    # move content to uploads/h5p/content/id
                    h5p_content_path = CONTENT_DIR / str(content.id)
                    h5p_content_path.mkdir()
                    Path(tmpdir / "content").rename(h5p_content_path / "content")
                    Path(tmpdir / "h5p.json").rename(h5p_content_path / "h5p.json")                   

                    

#    Except Exception as e:
#        print (e)

    #shutil.rmtree(tmpdir)
    return None


def process_update(h5p_file):
    tmpdir = Path(tempfile.mkdtemp())
    #try:
    file_path = h5p_file.h5p_file.file.name
    if 1 == 1:
        is_zipfile = zipfile.is_zipfile(file_path)
        if is_zipfile:
            with zipfile.ZipFile(file_path) as libzip:
                libzip.extractall(tmpdir)
            subdirs = get_subdirectories(tmpdir)
            libdirs = []
            for sd in subdirs:
                subdir_lib_path = Path(sd) / "library,json"
                if subdir_lib_path.isfile():
                    libdirs.append(sd)
            for ld in libdirs:
                library = process_library(ld)
    return
