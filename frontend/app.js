const uploadForm = document.getElementById('upload-form');
const imageFileInput = document.getElementById('image-file');
const statusPanel = document.getElementById('status-panel');
const statusText = document.getElementById('status-text');
const resultPanel = document.getElementById('result-panel');
const resultImage = document.getElementById('result-image');
const resultInfo = document.getElementById('result-info');
const thumbnailButton = document.getElementById('thumbnail-button');
const imageModal = document.getElementById('image-modal');
const originalImage = document.getElementById('original-image');
const modalClose = document.getElementById('modal-close');

const API_BASE = '/api';

function showStatus(message, percent = 0) {
  statusPanel.classList.remove('hidden');
  statusText.textContent = message;
  const bar = document.getElementById('progress-bar');
  bar.innerHTML = '';
  const fill = document.createElement('div');
  fill.style.width = `${percent}%`;
  bar.appendChild(fill);
}

function showResult(imageData) {
  resultPanel.classList.remove('hidden');
  resultImage.src = `${API_BASE}/images/${imageData.id}/thumbnail`;
  originalImage.src = `${API_BASE}/images/${imageData.id}/file`;
  resultInfo.innerHTML = `
    <p><strong>ID:</strong> ${imageData.id}</p>
    <p><strong>Status:</strong> ${imageData.status}</p>
    <p><strong>File:</strong> ${imageData.filename}</p>
    <p><strong>Width:</strong> ${imageData.width ?? 'N/A'}</p>
    <p><strong>Height:</strong> ${imageData.height ?? 'N/A'}</p>
    <p><strong>Camera model:</strong> ${imageData.camera_model ?? 'N/A'}</p>
  `;
}

function closeImageModal() {
  imageModal.classList.add('hidden');
}

thumbnailButton.addEventListener('click', () => {
  imageModal.classList.remove('hidden');
});

modalClose.addEventListener('click', closeImageModal);

imageModal.addEventListener('click', (event) => {
  if (event.target === imageModal) closeImageModal();
});

document.addEventListener('keydown', (event) => {
  if (event.key === 'Escape') closeImageModal();
});

async function pollImageStatus(imageId) {
  const startedAt = Date.now();
  const deadline = startedAt + 120000;

  while (Date.now() < deadline) {
    try {
      const response = await fetch(`${API_BASE}/images/${imageId}`);
      if (!response.ok) {
        throw new Error('Could not retrieve the image status');
      }

      const data = await response.json();
      showStatus(`Processing... Current status: ${data.status}`, 50);

      if (data.status === 'completed') {
        showStatus("Complete!", 100)
        showResult(data);
        return;
      }
    } catch (error) {
      console.error(error);
    }

    await new Promise(resolve => setTimeout(resolve, 2000));
  }

  showStatus('Processing is taking longer than expected. Check the status again later.', 100);
}

uploadForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  const file = imageFileInput.files[0];
  if (!file) return;

  showStatus('Uploading image...', 20);

  const formData = new FormData();
  formData.append('file', file);

  try {
    const response = await fetch(`${API_BASE}/images/upload`, {
      method: 'POST',
      body: formData,
    });

    if (!response.ok) {
      throw new Error('Could not upload the image');
    }

    const uploadData = await response.json();
    showStatus(`Image uploaded. Waiting for processing...`, 40);
    await pollImageStatus(uploadData.id);
  } catch (error) {
    console.error(error);
    showStatus('Could not upload or process the image', 100);
  }
});
