/**
 * Client-side image normalisation before upload.
 *
 * Two problems this solves at once:
 *  - Modern Android phones (and iPhones) often save photos as HEIC/HEIF.
 *    The backend's presigned-upload endpoint only accepts jpeg/png/webp/gif
 *    (see ALLOWED_CONTENT_TYPES in app/services/upload_service.py), so a
 *    HEIC file is rejected outright — before the request ever reaches R2.
 *  - Camera photos can be several MB; on a slow connection the direct PUT
 *    to R2 can stall or fail outright. Downscaling to the size AdsKinz
 *    actually recommends (1280×720) shrinks that dramatically.
 *
 * Re-encoding to JPEG via a canvas sidesteps both: whatever format came in,
 * what goes out is always a small, whitelisted image/jpeg file.
 */

const MAX_DIMENSION = 1280;
const JPEG_QUALITY = 0.85;

async function loadBitmap(file: File): Promise<ImageBitmap | HTMLImageElement> {
  if (typeof createImageBitmap === "function") {
    try {
      // Uses the platform's own image decoder — this is what lets Chrome on
      // Android decode HEIC here even though <img> support for HEIC is
      // inconsistent across browsers.
      return await createImageBitmap(file);
    } catch {
      // Fall through to the <img> based path below.
    }
  }
  const url = URL.createObjectURL(file);
  try {
    return await new Promise<HTMLImageElement>((resolve, reject) => {
      const img = new Image();
      img.onload = () => resolve(img);
      img.onerror = () => reject(new Error("Image could not be decoded."));
      img.src = url;
    });
  } finally {
    URL.revokeObjectURL(url);
  }
}

function sourceSize(src: ImageBitmap | HTMLImageElement): { width: number; height: number } {
  return "naturalWidth" in src
    ? { width: src.naturalWidth, height: src.naturalHeight }
    : { width: src.width, height: src.height };
}

/**
 * Re-encode `file` as a JPEG, downscaled so neither side exceeds
 * MAX_DIMENSION. Returns the original file unchanged if decoding fails
 * (best-effort — an already-small, already-supported file just passes
 * through the upload path as before) so this never blocks a valid upload.
 */
export async function normalizeImageForUpload(file: File): Promise<File> {
  let source: ImageBitmap | HTMLImageElement;
  try {
    source = await loadBitmap(file);
  } catch {
    return file;
  }

  const { width, height } = sourceSize(source);
  if (!width || !height) return file;

  const scale = Math.min(1, MAX_DIMENSION / Math.max(width, height));
  const targetWidth = Math.round(width * scale);
  const targetHeight = Math.round(height * scale);

  const canvas = document.createElement("canvas");
  canvas.width = targetWidth;
  canvas.height = targetHeight;
  const ctx = canvas.getContext("2d");
  if (!ctx) return file;
  ctx.drawImage(source as CanvasImageSource, 0, 0, targetWidth, targetHeight);
  if ("close" in source) source.close();

  const blob = await new Promise<Blob | null>((resolve) =>
    canvas.toBlob(resolve, "image/jpeg", JPEG_QUALITY),
  );
  if (!blob) return file;

  const newName = file.name.replace(/\.[^.]+$/, "") + ".jpg";
  return new File([blob], newName, { type: "image/jpeg" });
}
