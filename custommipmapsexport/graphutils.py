from pathlib import Path

import sd
from sd.api.sdvalueint2 import SDValueInt2
from sd.api.sdbasetypes import int2
from sd.api.sdproperty import SDPropertyCategory
from sd.api.sdvaluetexture import SDValueTexture


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
    
    
def save_test():
    """ This is a temporary function that's just a reminder. """
    sdContext = sd.getContext()
    pkgs = sdContext.getSDApplication().getPackageMgr().getUserPackages()
    pkg = [p for p in pkgs if p.getFilePath().endswith('MipLevels.sbs')][0]
    graph = pkg.findResourceFromUrl('mip_level_export')
    
    # Get property object and inheritance value.
    out_size_prp = graph.getPropertyFromId('$outputsize', SDPropertyCategory.Input)
    out_size_inheritance = graph.getPropertyInheritanceMethod(out_size_prp)   # Get inheritance.
    
    out_x, out_y = graph.getPropertyValue(out_size_prp).get()
    print('Output size: {}x{} px, {}'.format(2**out_x, 2**out_y, graph.getPropertyInheritanceMethod(out_size_prp)))
    
    graph.setPropertyValue(out_size_prp, SDValueInt2.sNew(int2(12, 12)))
    graph.compute()
    
    out_nodes = graph.getOutputNodes()
    dest_path = Path(__file__).resolve().parent / "res"
    
    for node in out_nodes:
        props = node.getProperties(SDPropertyCategory.Output)
        print(len(props))
        for prop in props:
            print(prop.getLabel())
            value = node.getPropertyValue(prop)
            sd_texture = SDValueTexture.get(value)
            dest_file = str(dest_path / f'{prop.getLabel()}.dds')
            sd_texture.save(dest_file)
