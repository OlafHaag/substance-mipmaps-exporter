import contextlib
import importlib.resources
import shutil
import subprocess
import tempfile
import time
from ctypes import string_at
from itertools import chain
from pathlib import Path
from typing import TypedDict

import sd
from custommipmapsexport.logger import logger
from sd.api.sbs.sdsbscompgraph import SDSBSCompGraph
from sd.api.sdbasetypes import int2
from sd.api.sdgraph import SDGraph
from sd.api.sdnode import SDNode
from sd.api.sdpackage import SDPackage
from sd.api.sdproperty import SDPropertyCategory, SDPropertyInheritanceMethod
from sd.api.sdtexture import SDTexture
from sd.api.sdvalueint2 import SDValueInt2
from sd.api.sdvaluetexture import SDValueTexture


def find_package_of_graph(graph: SDGraph) -> SDPackage | None:
    """
    Find the package of the given graph.

    Thanks to NevTD from substance3d forum.

    :param graph: The graph to find the package for.
    :return: The package containing the graph, or None if not found.
    """
    pkg_manager = sd.getContext().getSDApplication().getPackageMgr()
    return next((pkg for pkg in pkg_manager.getUserPackages() if pkg.findResourceFromUrl(graph.getUrl())), None)


def get_group_mapping(graph: SDGraph) -> dict[str, list[tuple[str, str]]]:
    """
    Return a dictionary with output groups as keys and node's identifier, uid (tuple) as values.

    :param graph: The graph to get the group mapping for.
    :return: A dictionary with output groups as keys and node's identifier, uid (tuple) as values.
    """
    outputs = graph.getOutputNodes()
    mapping: dict[str, list[tuple[str, str]]] = {}
    for out in outputs:
        group_value = out.getAnnotationPropertyValueFromId("group")
        group = group_value.get() if group_value is not None else "default"  # type: ignore[attr-defined]
        identifier = out.getProperties(SDPropertyCategory.Output)[0].getId()  # Seems hacky, but works.
        uid = out.getIdentifier()
        if group in mapping:
            mapping[group].append((identifier, uid))
        else:
            mapping[group] = [(identifier, uid)]
    return mapping


def get_output_name(graph: SDGraph, node_id: str, pattern: str) -> str:
    """
    Get the output name based on the given pattern.

    # pattern variables:
    $(graph) - name of current Graph.
    $(identifier) - identifier of current graph, from Graph Attributes.
    $(description) - description of current graph, from Graph Attributes.
    $(label) - Label of current graph, , from Graph Attributes.
    $(user_data) - custom user data, from Graph Attributes.
    $(group) - output group, from Graph Attributes.

    :param graph: The graph containing the node.
    :param node_id: The identifier of the node.
    :param pattern: The pattern to use for the output name.
    :return: The output name.
    """
    node = graph.getNodeFromId(node_id)
    if node is None:
        msg = f"Node with id {node_id} not found in the graph."
        raise ValueError(msg)

    mapping = {"$(graph)": graph.getIdentifier()}
    mapping["$(identifier)"] = node.getProperties(SDPropertyCategory.Output)[0].getId()
    mapping["$(description)"] = node.getAnnotationPropertyValueFromId("description").get()  # type:ignore[union-attr]
    mapping["$(label)"] = node.getAnnotationPropertyValueFromId("label").get()  # type:ignore[union-attr]
    mapping["$(user_data)"] = node.getAnnotationPropertyValueFromId("userdata").get()  # type:ignore[union-attr]
    group = node.getAnnotationPropertyValueFromId("group").get() or "default"  # type:ignore[union-attr]
    mapping["$(group)"] = group

    for k, v in mapping.items():
        pattern = pattern.replace(k, v)
    return pattern


def get_sd_tex(node: SDNode) -> SDTexture | None:
    """
    Get the SDTexture of the given node.

    :param node: The node to get the SDTexture for.
    :return: The SDTexture of the node.
    """
    prop = node.getProperties(SDPropertyCategory.Output)[0]  # Take the first output.
    value = node.getPropertyValue(prop)
    return SDValueTexture.get(value) if isinstance(value, SDValueTexture) else None


def get_tex_bytes(sd_tex: SDTexture) -> bytes:
    """
    Get the texture bytes of the given texture.

    :param sd_tex: The texture to get the bytes for.
    :return: The texture bytes.
    """
    dim_x, dim_y = sd_tex.getSize()  # type: ignore[attr-defined]  # Can unpack int2
    address = sd_tex.getPixelBufferAddress()
    return string_at(address, dim_x * dim_y * sd_tex.getBytesPerPixel())


def get_clamped_resolution(x: int, y: int, max_: int) -> tuple[int, int]:
    """
    Get the clamped resolution based on the given maximum resolution.

    :param x: The x resolution.
    :param y: The y resolution.
    :param max_: The maximum resolution.
    :return: The clamped resolution.
    """
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


def compress_files(files: list[Path], destination: Path, compression: str, **kwargs) -> int:
    """
    Compress the given files to the destination using the specified compression.

    :param files: The files to compress.
    :param destination: The destination to save the compressed files.
    :param compression: The compression method to use.
    :param kwargs: Additional arguments for the compression command.
    :return: The return code of the compression command.
    """
    crunch_app = importlib.resources.files("custommipmapsexport") / "bin" / "crunch_x64"
    cmd = [
        str(crunch_app),
        "-nostats",
        "-noprogress",
        *chain(*[("-file", str(f)) for f in files]),
        "-fileformat",
        "dds",
        "-outdir",
        str(destination),
        f"-{compression}",
        *chain(*kwargs.items()),
    ]
    with contextlib.suppress(ValueError):
        cmd.remove("")
    # Validate or sanitize the cmd list to ensure it contains only trusted input.
    if not all(isinstance(arg, str) for arg in cmd):
        msg = "Command contains non-string arguments."
        raise ValueError(msg)
    # This is a hobby project, so the user should be aware of the risks.
    completed = subprocess.run(cmd, capture_output=True, check=True)  # noqa: S603
    logger.info(completed.stdout.decode())
    return completed.returncode


class NodesData(TypedDict):
    """Dictionary to hold the data of the output nodes."""

    uids: list[str]
    nodes: list[SDNode]
    identifiers: list[str]
    basenames: list[str]


def get_nodes_data(graph: SDGraph, uids: list[str], pattern: str) -> NodesData:
    """
    Get the data of the nodes with the given uids.

    :param graph: The graph containing the nodes.
    :param uids: The uids of the nodes.
    :param pattern: The pattern to use for the output names.
    :return: A dictionary with the nodes data.
    """
    data: NodesData = {"uids": uids, "nodes": [], "identifiers": [], "basenames": []}

    for uid in uids:
        node = graph.getNodeFromId(uid)
        if not node:
            continue
        data["nodes"].append(node)
        data["identifiers"].append(node.getIdentifier())
        data["basenames"].append(get_output_name(graph, uid, pattern))
    return data


def save_textures(destination: Path, textures: list[SDTexture], names: list[str]) -> list[Path]:
    """
    Save the given textures to the destination with the specified names.

    :param destination: The destination to save the textures.
    :param textures: The textures to save.
    :param names: The names to use for the saved textures.
    :return: A list of file paths of the saved textures.
    """
    # ToDo: Parallelize saving with more than a few textures?
    #       Most classes and methods in Designer's Python API can only be called from the main application thread.
    #       Don't bother for now.
    files = []
    for i, tex in enumerate(textures):
        filepath = destination / f"{names[i]}.tga"
        tex.save(str(filepath))
        files.append(filepath)
    return files


def wait_files_exist(files: list[Path], timeout: float = 20.0, interval: float = 0.2) -> None:
    """
    Wait until all the given files exist.

    :param files: The files to wait for.
    :param timeout: The maximum time to wait.
    :param interval: The interval between checks.
    """
    all_files_exist = False
    while not all_files_exist:
        all_files_exist = all(f.is_file() for f in files)
        time.sleep(interval)
        timeout -= interval
        if timeout <= 0.0:
            break


def save_and_compress(
    intermediate_dir: Path,
    destination_dir: Path,
    textures: list[SDTexture],
    filenames: list[str],
    compression: str,
    **kwargs,
) -> str:
    """
    Save the textures to the intermediate directory and compress them to the destination directory.

    :param intermediate_dir: The intermediate directory to save the textures.
    :param destination_dir: The destination directory to save the compressed files.
    :param textures: The textures to save and compress.
    :param filenames: The filenames to use for the saved textures.
    :param compression: The compression method to use.
    :param kwargs: Additional arguments for the compression command.
    :return: A feedback message indicating the result of the operation.
    """
    # First, save to intermediate file when not compressing data ourselves.
    temp_files = save_textures(intermediate_dir, textures, filenames)
    # Make sure all temp files are saved before continuing to compression.
    wait_files_exist(temp_files)
    # Call program to compress saved files.
    return_code = compress_files(temp_files, destination_dir, compression, **kwargs)
    return "Export done" if return_code == 0 else "Error encountered. See console for details."


def export_dds_files(
    graph: SDSBSCompGraph,
    output_uids: list[str],
    destination: str | Path,
    pattern: str,
    compression: str,
    max_resolution: int | None = None,
    *,
    custom_lvls: bool = False,
    **kwargs,
) -> str:
    """
    Export DDS files from the given graph.

    :param graph: The graph to export the DDS files from.
    :param output_uids: The uids of the output nodes.
    :param destination: The destination to save the DDS files.
    :param pattern: The pattern to use for the output names.
    :param compression: The compression method to use.
    :param max_resolution: The maximum resolution for the output files.
    :param custom_lvls: Whether to use custom levels for the output files.
    :param kwargs: Additional arguments for the compression command.
    :return: A feedback message indicating the result of the operation.
    """
    out_data: NodesData = get_nodes_data(graph, output_uids, pattern)
    temp_dir = Path(tempfile.mkdtemp(prefix="SD_DDS_export_"))

    try:
        out_size_prp = graph.getPropertyFromId("$outputsize", SDPropertyCategory.Input)
        if out_size_prp is None:
            msg = "Output size property not found in the graph."
            raise ValueError(msg)

        out_size_value = graph.getPropertyValue(out_size_prp)
        if out_size_value is None:
            msg = "Output size value not found in the graph."
            raise ValueError(msg)

        out_x, out_y = out_size_value.get()  # type: ignore[attr-defined]   # log2
        out_size_inheritance = graph.getPropertyInheritanceMethod(out_size_prp)  # Get inheritance.

        if max_resolution:
            res_x, res_y = get_clamped_resolution(out_x, out_y, max_resolution)
            graph.setPropertyInheritanceMethod(out_size_prp, SDPropertyInheritanceMethod.Absolute)
            graph.setPropertyValue(out_size_prp, SDValueInt2.sNew(int2(res_x, res_y)))

        if custom_lvls:
            msg = "Export failed: Custom levels not implemented yet."
            raise NotImplementedError(msg)

        graph.compute()
        textures = [tex for node in out_data["nodes"] if (tex := get_sd_tex(node)) is not None]
        if not textures:
            msg = "No valid textures found in the graph nodes."
            raise ValueError(msg)

        feedback = save_and_compress(
            temp_dir, Path(destination), textures, out_data["basenames"], compression, **kwargs
        )

        if max_resolution:
            graph.setPropertyInheritanceMethod(out_size_prp, out_size_inheritance)
            graph.setPropertyValue(out_size_prp, SDValueInt2.sNew(int2(out_x, out_y)))
            graph.compute()

    except Exception as e:
        logger.error(f"An error occurred: {e}")
        feedback = (
            f"Export failed: Make sure you have write permissions for the destination folder:\n{destination}."
            "See console for details."
        )
    finally:
        shutil.rmtree(temp_dir)

    return feedback
