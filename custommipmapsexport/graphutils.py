from pathlib import Path
import shutil
from ctypes import string_at
from itertools import chain
import subprocess
import time

import sd
from sd.api.sdvalueint2 import SDValueInt2
from sd.api.sdbasetypes import int2
from sd.api.sdproperty import SDPropertyCategory, SDPropertyInheritanceMethod
from sd.api.sdvaluetexture import SDValueTexture

from .ddsfile import DDSFile


def find_package_of_graph(graph):
    # Thanks to NevTD from substance3d forum.
    pkg_manager = sd.getContext().getSDApplication().getPackageMgr()
    for pkg in pkg_manager.getUserPackages():
        if pkg.findResourceFromUrl(graph.getUrl()):
            return pkg
        

def get_group_mapping(graph):
    """ Return a dictionary with output groups as keys and node's identifier, uid (tuple) as values. """
    outputs = graph.getOutputNodes()
    mapping = dict()
    for out in outputs:
        group = out.getAnnotationPropertyValueFromId('group').get()
        if not group:
            group = 'default'
        identifier = out.getProperties(SDPropertyCategory.Output)[0].getId()  # Seems hacky, but works.
        uid = out.getIdentifier()
        if group in mapping:
            mapping[group].append((identifier, uid))
        else:
            mapping[group] = [(identifier, uid)]
            
    return mapping


def get_output_name(graph, node_id, pattern):
    """
    $(graph) - name of current Graph.
    $(identifier) - identifier of current graph, from Graph Attributes.
    $(description) - description of current graph, from Graph Attributes.
    $(label) - Label of current graph, , from Graph Attributes.
    $(user_data) - custom user data, from Graph Attributes.
    $(group) - output group, from Graph Attributes.
    """
    node = graph.getNodeFromId(node_id)
    mapping = dict()
    mapping['$(graph)'] = graph.getIdentifier()
    mapping['$(identifier)'] = node.getProperties(SDPropertyCategory.Output)[0].getId()
    mapping['$(description)'] = node.getAnnotationPropertyValueFromId('description').get()
    mapping['$(label)'] = node.getAnnotationPropertyValueFromId('label').get()
    mapping['$(user_data)'] = node.getAnnotationPropertyValueFromId('userdata').get()
    group = node.getAnnotationPropertyValueFromId('group').get()
    if not group:
        group = 'default'
    mapping['$(group)'] = group
    
    for k, v in mapping.items():
        pattern = pattern.replace(k, v)
    return pattern
    
    
def get_sd_tex(node):
    prop = node.getProperties(SDPropertyCategory.Output)[0]  # Take the first output.
    value = node.getPropertyValue(prop)
    sd_texture = SDValueTexture.get(value)
    return sd_texture


def get_tex_bytes(sd_tex):
    dim_x, dim_y = sd_tex.getSize()
    address = sd_tex.getPixelBufferAddress()
    tex_b = string_at(address, dim_x * dim_y * sd_tex.getBytesPerPixel())
    return tex_b


def get_clamped_resolution(x, y, max_):
    xy_diff = x - y
    if xy_diff == 0:
        res_x = res_y = max_
    elif xy_diff >= 0:
        res_x = max_
        res_y = max_ - xy_diff
    else:
        res_y = max_
        res_x = max_ + xy_diff  # Difference is negative.
    return res_x, res_y


def compress_files(files, destination, compression, **kwargs):
    crunch_app = Path(__file__).resolve().parent / 'bin' / 'crunch_x64'
    cmd = [str(crunch_app),
           '-nostats',
           '-noprogress',
           *chain(*[('-file', str(f)) for f in files]),
           '-fileformat', 'dds',
           '-outdir', str(destination),
           f'-{compression}',
           *chain(*kwargs.items())]
    try:
        cmd.remove('')
    except ValueError:
        pass
    completed = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    print(completed.stdout.decode())
    return completed.returncode


def get_nodes_data(graph, uids, pattern):
    data = {'uids': uids,
            'nodes': [],
            'identifiers': [],
            'basenames': [],
            'textures': []}
    
    for uid in uids:
        node = graph.getNodeFromId(uid)
        data['nodes'].append(node)
        data['identifiers'].append(node.getIdentifier())
        data['basenames'].append(get_output_name(graph, uid, pattern))
    return data
    
    
def save_textures(destination, textures, names):
    # ToDo: Parallelize saving with more than 2 textures.
    files = list()
    for i, tex in enumerate(textures):
        filepath = destination / (names[i] + ".tga")
        tex.save(str(filepath))
        files.append(filepath)
    return files


def wait_files_exist(files, timeout=20.0, interval=0.2):
    all_files_exist = False
    while not all_files_exist:
        all_files_exist = all([f.is_file() for f in files])
        time.sleep(interval)
        timeout -= interval
        if timeout <= 0.0:
            break


def save_and_compress(intermediate_dir, destination_dir, textures, filenames, compression, **kwargs):
    # First, save to intermediate file when not compressing data ourselves.
    temp_files = save_textures(intermediate_dir, textures, filenames)
    # Make sure all temp files are saved before continuing to compression.
    wait_files_exist(temp_files)
    # Call program to compress saved files.
    return_code = compress_files(temp_files, destination_dir, compression, **kwargs)
    if return_code == 0:
        feedback = "Export done"
    else:
        feedback = "Error encountered. See console for details."
    return feedback


def export_dds_files(graph, output_uids, destination, pattern, compression, max_resolution=None, custom_lvls=False,
                     **kwargs):
    out_data = get_nodes_data(graph, output_uids, pattern)
    
    # Create path if it doesn't exist.
    # Also create temporary directory to save intermediate files.
    temp_dir = (Path(destination) / ".tmp_export/")
    try:
        temp_dir.mkdir(parents=True, exist_ok=True)
    except IOError:
        # When creating temp dir fails, abort and give feedback.
        feedback = "Failed to export paths:\n" + "\n".join([str(Path(destination) / (n + ".dds"))
                                                            for n in out_data['basenames']])
        return feedback
        
    # Get property object and inheritance value.
    out_size_prp = graph.getPropertyFromId('$outputsize', SDPropertyCategory.Input)
    out_x, out_y = graph.getPropertyValue(out_size_prp).get()  # log2
    out_size_inheritance = graph.getPropertyInheritanceMethod(out_size_prp)   # Get inheritance.
    
    # Handle case where maximum resolution was set.
    if max_resolution:
        res_eq_max = (max_resolution in (out_x, out_y)) and (max_resolution == max(out_x, out_y))  # FixMe: Doesn't work with relative inheritance
        # Get new size.
        res_x, res_y = get_clamped_resolution(out_x, out_y, max_resolution)
        if not res_eq_max:
            # Set inheritance to absolute, so we can set the resolution.
            graph.setPropertyInheritanceMethod(out_size_prp, SDPropertyInheritanceMethod.Absolute)
            graph.setPropertyValue(out_size_prp, SDValueInt2.sNew(int2(res_x, res_y)))
    else:
        res_eq_max = True
        
    # When no customization is set, export and auto-generate MIP levels.
    if not custom_lvls:
        # Make sure all the texture data is there.
        graph.compute()
        textures = [get_sd_tex(node) for node in out_data['nodes']]
        feedback = save_and_compress(temp_dir, destination, textures, out_data['basenames'], compression, **kwargs)
    
    else:
        # ToDo: custom levels.
        '''
        # Create DDS for each resolution and stitch together.
        for res in range(max_resolution, -1, -1):
            # ToDo: Support non-square
            graph.setPropertyValue(out_size_prp, SDValueInt2.sNew(int2(res_x, res_y)))
            graph.compute()
            # Get binary data from each output
            # Compress
            # add to dds
        # Write DDS to file.
        '''
        feedback = "Not implemented yet"
    
    # Return graph to original resolution and inheritance if it was changed.
    if (not res_eq_max) or custom_lvls:
        graph.setPropertyInheritanceMethod(out_size_prp, out_size_inheritance)
        graph.setPropertyValue(out_size_prp, SDValueInt2.sNew(int2(out_x, out_y)))
        graph.compute()
    
    # Delete temp folder with contents.
    shutil.rmtree(temp_dir)
    return feedback
