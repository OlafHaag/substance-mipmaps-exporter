# DDS Exporter Plugin with custom MipMaps for Substance Designer

When exporting to a direct draw surface (DDS) from Substance Designer, MipMap generation and compression are not supported.

The settings for MipMaps generation in Designer only serve as a marker for third party software integrations of the Substance Engine.
The output compression setting is only used when the substance file is rendered by the Substance Engine in a game engine integration.
It has no influence on the generation of dds files in Designer. 

This plugin aims to work around that issue.  
It does so by writing out the textures to an intermediate file format and
then uses crunch (modified by [Unity-Technologies](https://github.com/Unity-Technologies/crunch/tree/unity)) to convert to dds. It's therefore a simple GUI wrapper for crunch.

It would be nice to do the compression on the binary texture data directly instead of first writing files
as an intermediate step before compression. 

crunch/crnlib v1.04 - Advanced DXTn texture compression library Copyright (C) 2010-2017 Richard Geldreich, Jr. and Binomial LLC http://binomial.info

This project is currently __under early development__.
