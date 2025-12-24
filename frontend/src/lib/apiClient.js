const API_BASE_URL = import.meta.env.VITE_API_BASE_URL || '';
if (!API_BASE_URL) {
  console.warn('[API] Missing VITE_API_BASE_URL configuration');
}

const buildUrl = (path) => {
  if (!API_BASE_URL) {
    throw new Error('Missing VITE_API_BASE_URL configuration');
  }
  return `${API_BASE_URL}${path}`;
};

const buildHeaders = (token, extra = {}) => {
  if (!token) {
    throw new Error('Missing access token');
  }
  return {
    'Content-Type': 'application/json',
    Authorization: `Bearer ${token}`,
    ...extra,
  };
};

const handleResponse = async (response, info) => {
  if (response.status === 204) {
    return null;
  }
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const errorMessage = data?.detail || `Request failed (${info.method} ${info.path})`;
    console.error('[API] Error', info, 'status=', response.status, 'body=', data);
    throw new Error(errorMessage);
  }
  return data;
};

const fetchWithDiagnostics = async (path, options, methodLabel) => {
  const warnTimeout = setTimeout(() => {
    console.warn(`[API][pending] ${methodLabel} ${path}`);
  }, 5000);
  try {
    const response = await fetch(buildUrl(path), options);
    clearTimeout(warnTimeout);
    return response;
  } catch (err) {
    clearTimeout(warnTimeout);
    console.error(`[API] Network error ${methodLabel} ${path}`, err);
    throw err;
  }
};

export const apiGet = async (path, token) => {
  const response = await fetchWithDiagnostics(
    path,
    {
      headers: buildHeaders(token),
    },
    'GET'
  );
  return handleResponse(response, { method: 'GET', path });
};

export const apiPost = async (path, body, token) => {
  const response = await fetchWithDiagnostics(
    path,
    {
      method: 'POST',
      headers: buildHeaders(token),
      body: JSON.stringify(body),
    },
    'POST'
  );
  return handleResponse(response, { method: 'POST', path });
};

export const apiDelete = async (path, token) => {
  const response = await fetchWithDiagnostics(
    path,
    {
      method: 'DELETE',
      headers: buildHeaders(token),
    },
    'DELETE'
  );
  return handleResponse(response, { method: 'DELETE', path });
};
