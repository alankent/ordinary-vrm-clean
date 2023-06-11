# VRM Importer for NVIDIA Omniverse

This repository is a work in progress, but making it available in its
current messy form regardless. I hope to clean this up and improve it
over the coming months.

## What is NVIDIA Omniverse

You can download NVIDIA Omniverse for free if you have a NVIDIA GPU.
You can create 3D scenes using USD (Universal Scene Description) originally
from Pixar, now open source (https://openusd.org/).
Omniverse uses USD as its native file format.

## What is this repo?

This repo contains a Omniverse Kit extension. Almost all the Omniverse
tools are built using Kit, their framework for app building.
See [README-ext.md](./README-ext.md) for more information.

This extension is not in a good or final place, but I got it to do something
so sharing with the world in case anyone else wants to give it a go.

## The UI looks like the default template extension UI

Well spotted. I have put no effort into the UI at this stage. I just wanted
to get it to do something. So there is a button called "Clean" which runs
the code and "Dump" which walks the current Stage and prints out the length
of all properties that hold arrays. (I was use the latter to work out the
lengths of all the point mesh details as part of my learnings.)

## So how do I use it?

I grab a `.vrm` file exported from [VRoid Studio](https://vroid.com/en/studio),
rename it to `.glb`, open in Omniverse USD Composer (formerly "Create"),
right click and "Convert to USD". I then open the USD file and click the
"Clean" button. It restructures things in the currently opened character
USD file.

[VRM](https://github.com/vrm-c) files are in GLB format (the binary form of
glTF) but follow some additional standards to help with interchange in VR apps
(like VR Chat and some VTuber software like [VSeeFace](https://vseeface.icu).

Ultimately, I could imagine this extension becoming a `.vrm` file importer
extension for Omniverse. One day...

## Why is it necessary?

Using the above approach to import a GLB file has worked the best but
still suffers from problems in Omniverse:

* The root bone is lost during the GLB import process, making animation clips not work correctly
* [Audio2Face](https://www.nvidia.com/en-us/omniverse/apps/audio2face/) does not like the meshes VRoid Studio generates
* Need to add hair physics (not started)
* Need to add cloth physics for clothes, like skirts (not started)

## Why am I doing this?

I tell people I am trying to create an animated cartoon series to publish
on YouTube. What really happens is I get distracted geeking out on technology.

* I created a few episodes originally with 2D animation in Adobe Character Animator.
* I then created a few episodes using Unity as the rendering pipeline (HDRP).
* I am now exploring NVIDIA Omniverse for rendering.

I am trying to stick to free tools so others can give it a go and see if
they like it before investing money into commercial tools.

## When can I learn more?

I blog at [extra-ordinary.tv/blog](https://extra-ordinary.tv/blog/)

* [First Steps for VRoid Studio characters in NVIDIA Omniverse](https://extra-ordinary.tv/2023/05/28/2902/)
* [VRoid Studio, meet NVIDIA Omniverse](https://extra-ordinary.tv/2023/05/10/vroid-studio-meet-nvidia-omniverse/)
