# Generating OG images from screenshots

The images that are captured for the detailed Showcase pages of the site are generally 1920x1080 pixels. However that size does not work well for an OG image when I share a particular Showcase page on social media. This document outlines how I would like to see that change.

## Where to generate the OG images

The ideal place to generate the OG images would be as part of the initial screenshot capture process. This would allow us to generate the OG image at the same time as the main screenshot, and ensure that the OG image is always up to date with the latest version of the Showcase page.

## OG image sizes

Since OG images are ideally 1200x630 pixels, the captured screenshots would need to be resized and appropriately cropped to fit that aspect ratio. This would ensure that the OG images look good when shared on social media, and that they accurately represent the content of the Showcase page. My suggestion would be to resize the captured screenshots to 1200 pixels wide, and then crop the height to 630 pixels, trimming excess from the bottom of the resulting resized image, ensuring that the top of the image is preserved, as that is where the most important content of the Showcase page is located.

## OG image naming convention

There exists an current convention for generating the names of the screenshots based on the url of the site being showcased. This is followed by a '-large' suffix to indicate that it is the large version of the screenshot.

I would propose that the OG images follow a similar naming convention, but with an '-og' suffix instead of '-large'. For example, if the screenshot for a particular Showcase page is named 'example-com-large.png', the corresponding OG image would be named 'example-com-og.png'.

## Where to store the OG images

Similar to the way screenshots are stored in the content/screenshots directory of the 11tybundle.dev project, a project located under the sibling folder '11tybundle', the OG images should be stored in a similar directory structure, perhaps in a content/og-images directory. This would allow us to easily reference the OG images in the Showcase page templates, and ensure that they are organized in a consistent way.

Upon capture, this project also stores screenshots in another directory, specifically located at 11tybundle/11tybundledb/screenshots, which is a separate project that serves as a database for 11tybundle.dev project and related metadata. The OG images should also be stored in there, in an og-images directory.

## Caveats

1. How best to go about generating OG images from all of the existing showcase images.

2. The 11tybundle.dev project would need to be updated to refer to these images when generating the meta tags for the OG images, but only for the Showcase detail pages. I will undertake a separate effort to ensure that happens once the og images are in place.
