# DDS Exporter Plugin with custom Mipmaps for Substance Designer

When exporting to a direct draw surface (DDS) from Substance Designer, mipmap generation and compression are not supported.

The settings for mipmaps generation in Designer only serve as a marker for third party software integrations of the Substance Engine.
The output compression setting is only used when the substance file is rendered by the Substance Engine in a game engine integration.
It has no influence on the generation of dds files in Designer.

This plugin aims to work around that issue.  
It does so by writing out the textures to an intermediate file format and
then uses crunch (modified by [Unity-Technologies](https://github.com/Unity-Technologies/crunch/tree/unity)) to convert to dds. It's therefore a simple GUI wrapper for crunch.  
See it in action: <https://youtu.be/T8MZ-Wr7OiM>

## Installation

Download the latest release from the [release page](https://github.com/OlafHaag/substance-mipmaps-exporter/releases)
Expand the *Assets* dropdown and download the *.sdplugin* file.  
In Substance Designer's top-bar menu go to *Tools->Plugin Manager...*. In the dialog choose *INSTALL...*. Browse to the file you just downloaded.  
If necessary, activate the *LOADED* checkbox. When you open a graph view the new plugin icon appears.

## Planned Features

- Support custom MIP levels. You can set your network up to change the output depending on the graph's resolution (see example folder).
I'd like to stitch the lower resolution outputs as custom MIP levels into a dds file.

It would also be nice to do the compression on the texture data directly instead of first writing files
as an intermediate step before compression. But I don't see that happening any time soon.

## Acknowledgment

crunch/crnlib v1.04 - Advanced DXTn texture compression library Copyright (C) 2010-2017 Richard Geldreich, Jr. and Binomial LLC <http://binomial.info>
