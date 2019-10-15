from pathlib import Path

import sd
from sd.api.sdvalueint2 import SDValueInt2
from sd.api.sdbasetypes import int2
from sd.api.sdproperty import SDPropertyCategory
from sd.api.sdvaluetexture import SDValueTexture


def save_test():
    """ This is a temporary function that's just a reminder. """
    sdContext = sd.getContext()
    pkgs = sdContext.getSDApplication().getPackageMgr().getUserPackages()
    pkg = [p for p in pkgs if p.getFilePath().endswith('MipLevels.sbs')][0]
    graph = pkg.findResourceFromUrl('mip_level_export')
    
    # Get property object and inheritance value.
    out_size_prp = graph.getPropertyFromId('$outputsize', sd.api.sdproperty.SDPropertyCategory.Input)
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
