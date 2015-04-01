#!/usr/bin/env python
"""
Extracts data from xnat archive folders into a few well-known formats.

Usage: 
    extract.py [options] <archivedir>...

Arguments:
    <archivedir>            Path to scan folder within the XNAT archive

Options: 
    --datadir DIR           Parent folder to extract to [default: ./data]
    --exportinfo FILE       Table listing acquisitions to export by format
                            [default: ./metadata/protocols.csv]
    --debug                 Show debug messages
    -n, --dry-run           Do nothing

INPUT FOLDERS
    The <archivedir> is the XNAT archive directory to extract from. This should
    point to a single scan folder, and the folder should be named according to
    our data naming scheme. For example, 

        /xnat/spred/archive/SPINS/arc001/SPN01_CMH_0001_01_01

    This folder is expected to have the following subfolders: 

    SPN01_CMH_0001_01_01/
      RESOURCES/                    (optional)
        *                           (optional non-dicom data)
      SCANS/
        001/                        (series #)
          DICOM/       
            *                       (dicom files, usually named *.dcm) 
            scan_001_catalog.xml
        002/
        ...

OUTPUT FOLDERS
    Each dicom series will be converted and placed into a subfolder of the
    datadir named according to the converted filetype and subject ID, e.g. 

        data/
            nifti/
                SPN01_CMH_0001/
                    (all nifti acquisitions for this subject)
    
OUTPUT FILE NAMING
    Each dicom series will be and named according to the following schema: 

        <scanid>_<tag>_<series#>_<description>.<ext>

    Where, 
        <scanid>  = the scan id from the file name, eg. DTI_CMH_H001_01_01
        <tag>     = a short code indicating the data type (e.g. T1, DTI, etc..)
        <series#> = the dicom series number in the exam
        <descr>   = the dicom series description 
        <ext>     = appropriate filetype extension

    For example, a T1 in nifti format might be named: 
        
        DTI_CMH_H001_01_01_T1_11_Sag-T1-BRAVO.nii.gz

    The <tag> field is looked up in the export info table (e.g.
    protocols.csv), see below. 
    
EXPORT TABLE FORMAT
    This export table (specified by --exportinfo) file should contain lookup
    table that supplies a pattern to match against the DICOM SeriesDescription
    header and corresponding tag name. Additionally, the export table should
    contain a column for each export filetype with "yes" if the series should
    be exported to that format. 

    For example:

    pattern       tag     export_mnc  export_nii  export_nrrd  count
    Localiser     LOC     no          no          no           1
    Calibration   CAL     no          no          no           1
    Aniso         ANI     no          no          no           1
    HOS           HOS     no          no          no           1
    T1            T1      yes         yes         yes          1
    T2            T2      yes         yes         yes          1
    FLAIR         FLAIR   yes         yes         yes          1
    Resting       RES     no          yes         no           1
    Observe       OBS     no          yes         no           1
    Imitate       IMI     no          yes         no           1
    DTI-60        DTI-60  no          yes         yes          3
    DTI-33-b4500  b4500   no          yes         yes          1
    DTI-33-b3000  b3000   no          yes         yes          1
    DTI-33-b1000  b1000   no          yes         yes          1

NON-DICOM DATA
    XNAT puts "other" (i.e. non-DICOM data) into the RESOURCES folder. This
    data will be copied to a subfolder of the data directory named
    resources/<scanid>, for example: 

        resources/SPN01_CMH_0001_01_01/
    
    In addition to the data in RESOURCES, the *_catalog.xml file from each scan
    series will be placed in the resources folder with the output file naming
    listed above, e.g. 

        resources/SPN01_CMH_0001_01_01/
            SPN01_CMH_0001_01_01_CAT_001_catalog.xml
            SPN01_CMH_0001_01_01_CAT_002_catalog.xml
            ... 

EXAMPLES

    xnat-extract.py /xnat/spred/archive/SPINS/arc001/SPN01_CMH_0001_01_01

"""
from docopt import docopt
import pandas as pd
import datman as dm
import datman.utils
import datman.scanid
import os.path
import sys
import tempfile
import glob

DEBUG  = False
DRYRUN = False
def error(message): 
    print "ERROR:", message
    sys.stdout.flush()

def log(message): 
    print message
    sys.stdout.flush()

def debug(message): 
    if not DEBUG: return
    print "DEBUG:",message
    sys.stdout.flush()

def makedirs(path):
    debug("makedirs: {}".format(path))
    if not DRYRUN: os.makedirs(path)

def system(cmd):
    debug("exec: {}".format(cmd))
    if not DRYRUN: os.system(cmd)

def main():
    global DEBUG 
    global DRYRUN
    arguments = docopt(__doc__)
    archives       = arguments['<archivedir>']
    exportinfofile = arguments['--exportinfo']
    datadir        = arguments['--datadir']
    DEBUG          = arguments['--debug']
    DRYRUN         = arguments['--dry-run']

    exportinfo = pd.read_table(exportinfofile, sep='\s*', engine="python")

    for archivepath in archives:
        extract_archive(exportinfo, archivepath, datadir)


def extract_archive(exportinfo, archivepath, exportpath):
    """
    Exports an XNAT archive to various file formats.

    The <archivepath> is the XNAT archive directory to extract from. This
    should point to a single scan folder, and the folder should be named
    according to our data naming scheme. 

    This function searches through the SCANS subfolder (archivepath) for series
    and converts each series, placing them in an appropriately named folder
    under export_path. 
    """

    # get basic exam info
    basename = os.path.basename(archivepath)

    if not datman.scanid.is_scanid(basename):
        error("{} folder is not named according to the data naming policy. " \
              "Skipping".format(archivepath))
        return

    scanid    = datman.scanid.parse(basename)

    scanspath = os.path.join(archivepath,'SCANS')
    if not os.path.isdir(scanspath):
        error("{} doesn't exist. Not an XNAT archive. "\
              "Skipping.".format(scanspath))
        return

    headers = dm.utils.get_archive_headers(archivepath)

    # get export info for the exam study code 
    study_headers = headers.values()[0]                     # arbitrary header
    formats       = get_formats_from_exportinfo(exportinfo)
    unknown_fmts  = [fmt for fmt in formats if fmt not in exporters]

    if len(unknown_fmts) > 0: 
        error("Unknown formats requested for export of {}: {}. " \
              "Skipping.".format(archivepath, ",".join(unknown_fmts)))
        return

    # export each series
    log("Exporting series from {}".format(archivepath))
    for path, header in headers.iteritems():
        export_series(exportinfo, path, header, formats, scanid, exportpath)

    export_resources(archivepath, exportpath, scanid)

def export_series(exportinfo, seriesdir, header, formats, scanid, exportpath):
    """
    Exports the given DICOM folder into the given formats.
    """
    description   = header.get("SeriesDescription")
    mangled_descr = dm.utils.mangle(description)
    series        = str(header.get("SeriesNumber")).zfill(2)
    tagmap        = dict(zip(exportinfo['pattern'].tolist(),
                             exportinfo['tag'].tolist()))
    tag           = dm.utils.guess_tag(mangled_descr, tagmap)

    debug("{}: description = {}, series = {}, tag = {}".format(
        seriesdir, description, series, tag))

    if not tag or type(tag) is list: 
        error("{}: Unknown series tag for description: {}, tag = {}".format(
            seriesdir, description, tag))
        return

    tag_exportinfo = exportinfo[exportinfo['tag'] == tag]
    subjectid = "_".join([scanid.study,scanid.site,scanid.subject])
    filestem  = "_".join([str(scanid),tag,series,mangled_descr]) 

    for fmt in formats:
        if all(tag_exportinfo['export_'+fmt] == 'no'):
            debug("{}: export_{} set to 'no' for tag {} so skipping".format(
                seriesdir, fmt, tag))
            continue

        outputdir  = os.path.join(exportpath,fmt,subjectid)
        if not os.path.exists(outputdir): makedirs(outputdir)

        exporters[fmt](seriesdir,outputdir,filestem)


def get_formats_from_exportinfo(dataframe):
    """
    Gets the export formats from the column names in an exportinfo table.

    Columns that begin with "export_" are extracted, and the format identifier
    from each column is returned, as a list. 
    """

    columns = dataframe.columns.values.tolist()
    formats = [c.split("_")[1] for c in columns if c.startswith("export_")]
    return formats

def export_resources(archivepath, exportpath, scanid):
    """
    Exports all the non-dicom resources for an exam archive.
    """
    log("Exporting non-dicom stuff from {}".format(archivepath))
    sourcedir = os.path.join(archivepath, "RESOURCES")
    outputdir = os.path.join(exportpath,"RESOURCES",str(scanid))
    if not os.path.exists(outputdir): makedirs(outputdir)
    system("rsync -a {}/ {}/".format(sourcedir, outputdir))

def export_mnc_command(seriesdir,outputdir,filestem):
    """
    Returns a commandline to convert a DICOM series to MINC format
    """
    outputfile = os.path.join(outputdir,filestem) + ".mnc"

    if os.path.exists(outputfile):
        debug("{}: output {} exists. skipping.".format(
            seriesdir, outputfile))
        return

    debug("{}: exporting to {}".format(seriesdir, outputfile))
    cmd = 'dcm2mnc -fname {} -dname "" {}/* {}'.format(
            filestem,seriesdir,outputdir)
    system(cmd)

def export_nii_command(seriesdir,outputdir,filestem):
    """
    Returns a commandline to convert a DICOM series to NifTi format
    """
    outputfile = os.path.join(outputdir,filestem) + ".nii.gz"

    if os.path.exists(outputfile):
        debug("{}: output {} exists. skipping.".format(
            seriesdir, outputfile))
        return

    debug("{}: exporting to {}".format(seriesdir, outputfile))

    # convert into tempdir
    tmpdir = tempfile.mkdtemp()
    system('dcm2nii -x n -g y  -o {} {}'.format(tmpdir,seriesdir))

    # move nii in tempdir to it's proper location
    for f in glob.glob("{}/*".format(tmpdir)):
        bn = os.path.basename(f)
        ext = dm.utils.get_extension(f)
        if bn.startswith("o") or bn.startswith("co"): continue
        system("mv {} {}/{}{}".format(f, outputdir, filestem, ext))

def export_nrrd_command(seriesdir,outputdir,filestem):
    """
    Returns a commandline to convert a DICOM series to NRRD format
    """
    outputfile = os.path.join(outputdir,filestem) + ".nrrd"

    if os.path.exists(outputfile):
        debug("{}: output {} exists. skipping.".format(
            seriesdir, outputfile))
        return

    debug("{}: exporting to {}".format(seriesdir, outputfile))

    cmd = 'DWIConvert -i {} --conversionMode DicomToNrrd -o {}.nrrd ' \
          '--outputDirectory {}'.format(seriesdir,filestem,outputdir)

    system(cmd)

exporters = {
    "mnc" : export_mnc_command,
    "nii" : export_nii_command,
    "nrrd": export_nrrd_command,
}

if __name__ == '__main__':
    main()

# vim: ts=4 sw=4: