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


def compress_files(files, destination, compression):
    crunch_app = Path(__file__).resolve().parent / 'bin' / 'crunch_x64'
    cmd = [str(crunch_app),
           '-nostats',
           *chain(*zip(('-file',)*len(files), (str(f) for f in files))),
           '-fileformat', 'dds',
           '-outdir', str(destination),
           f'-{compression}']
    completed = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if completed.returncode != 0:
        print(completed.stdout.decode())
    return completed.returncode


def export_dds_files(graph, output_uids, destination, pattern, compression, max_resolution=None, custom_lvls=False):
    # ToDo: When export successful, feedback "Export done".
    
    out_names = dict(map(lambda uid: (uid, get_output_name(graph, uid, pattern)), output_uids))
    nodes = [graph.getNodeFromId(uid) for uid in output_uids]
    sd_textures = [get_sd_tex(node) for node in nodes]
    
    # Create path if it doesn't exist.
    # Also create temporary directory to save intermediate files.
    temp_dir = (Path(destination) / ".tmp_export/")
    try:
        temp_dir.mkdir(parents=True, exist_ok=True)
    except IOError:
        # ToDo: When creating file fails, give feedback in GUI.
        print("Failed to export paths:\n" + "\n".join([str(Path(destination) / (n + ".dds"))
                                                       for n in out_names.values()]))
        return
        
    # When no customization is set, export and compress as is.
    if (not max_resolution) and (not custom_lvls):
        # Make sure all the data is there.
        graph.compute()
        # ToDo: Parallelize saving with more than 2 textures.
        # First, save to uncompressed file when not compressing data ourselves.
        temp_files = list()
        for i, tex in enumerate(sd_textures):
            tmp_out = temp_dir / (out_names[nodes[i].getIdentifier()] + ".tga")
            tex.save(str(tmp_out))
            temp_files.append(tmp_out)
        
        time.sleep(1)  # ToDo: Make sure files are written before continuing.
        # Call program to compress saved files.
        return_code = compress_files(temp_files, destination, compression)
        
    else:
        # Get property object and inheritance value.
        out_size_prp = graph.getPropertyFromId('$outputsize', SDPropertyCategory.Input)
        out_x, out_y = graph.getPropertyValue(out_size_prp).get()  # log2
        out_size_inheritance = graph.getPropertyInheritanceMethod(out_size_prp)   # Get inheritance.
        print(f'Output size: {2 ** out_x}x{2 ** out_y} px, {graph.getPropertyInheritanceMethod(out_size_prp)}')
        
        if max_resolution:
            res_eq_max = max_resolution == max((out_x, out_y, max_resolution))
            # Get new size.
            res_x, res_y = get_clamped_resolution(out_x, out_y, max_resolution)
        else:
            res_eq_max = True
            res_x, res_y = out_x, out_y  # FixMe: When relative, res == 0? Get real size.
            
        if (not res_eq_max) or custom_lvls:
            # Set inheritance to absolute, so we can set the resolution.
            graph.setPropertyInheritanceMethod(out_size_prp, SDPropertyInheritanceMethod.Absolute)
            graph.setPropertyValue(out_size_prp, SDValueInt2.sNew(int2(res_x, res_y)))
        # Make sure all the data is there.
        graph.compute()
        
        if custom_lvls:
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
            pass
        else:
            # ToDo: Save outputs to temporary files.
            # ToDo: Subprocess crunch files
            pass
        
        # Return graph to original resolution and inheritance if it was changed.
        if (not res_eq_max) or custom_lvls:
            graph.setPropertyInheritanceMethod(out_size_prp, out_size_inheritance)
            graph.setPropertyValue(out_size_prp, SDValueInt2.sNew(int2(out_x, out_y)))
            graph.compute()
    
    # Delete temp folder with contents.
    shutil.rmtree(temp_dir)
