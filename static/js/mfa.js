(() => {
    const csrf = document.querySelector('meta[name="csrf-token"]')?.content;
    const jsonFetch = async (url, options = {}) => {
        const headers = {'Content-Type': 'application/json', ...(options.headers || {})};
        if (csrf) headers['X-CSRFToken'] = csrf;
        const response = await fetch(url, {...options, headers});
        const data = await response.json();
        if (!response.ok) throw new Error(data.error || 'Request failed');
        return data;
    };
    const decode = value => Uint8Array.from(atob(value.replace(/-/g, '+').replace(/_/g, '/') + '='.repeat((4 - value.length % 4) % 4)), c => c.charCodeAt(0));
    const encode = value => btoa(String.fromCharCode(...new Uint8Array(value))).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '');
    const credentialJSON = credential => ({
        id: credential.id, rawId: encode(credential.rawId), type: credential.type,
        authenticatorAttachment: credential.authenticatorAttachment,
        clientExtensionResults: credential.getClientExtensionResults(),
        response: credential.response.attestationObject ? {
            attestationObject: encode(credential.response.attestationObject),
            clientDataJSON: encode(credential.response.clientDataJSON),
            transports: credential.response.getTransports?.() || [],
        } : {
            authenticatorData: encode(credential.response.authenticatorData),
            clientDataJSON: encode(credential.response.clientDataJSON),
            signature: encode(credential.response.signature),
            userHandle: credential.response.userHandle ? encode(credential.response.userHandle) : null,
        }
    });
    const output = document.getElementById('mfa-output');
    document.getElementById('totp-start')?.addEventListener('click', async () => {
        try {
            const data = await jsonFetch('/api/mfa/totp/start', {method: 'POST', body: '{}'});
            document.getElementById('totp-secret').textContent = data.secret;
            document.getElementById('totp-uri').textContent = data.provisioning_uri;
            document.getElementById('totp-details').hidden = false;
        } catch (error) { output.textContent = error.message; }
    });
    document.getElementById('totp-verify')?.addEventListener('click', async () => {
        try {
            const code = document.getElementById('totp-code').value;
            const data = await jsonFetch('/api/mfa/totp/verify', {method: 'POST', body: JSON.stringify({code})});
            output.textContent = `Save these recovery codes now; they are shown once:\n${data.recovery_codes.join('\n')}`;
        } catch (error) { output.textContent = error.message; }
    });
    document.getElementById('passkey-register')?.addEventListener('click', async () => {
        try {
            const options = await jsonFetch('/api/mfa/passkeys/register/options', {method: 'POST', body: '{}'});
            options.challenge = decode(options.challenge);
            options.user.id = decode(options.user.id);
            options.excludeCredentials = (options.excludeCredentials || []).map(c => ({...c, id: decode(c.id)}));
            const credential = await navigator.credentials.create({publicKey: options});
            const data = await jsonFetch('/api/mfa/passkeys/register/verify', {method: 'POST', body: JSON.stringify({name: document.getElementById('passkey-name').value, credential: credentialJSON(credential)})});
            output.textContent = data.recovery_codes ? `Save these recovery codes now; they are shown once:\n${data.recovery_codes.join('\n')}` : 'Passkey enrolled.';
        } catch (error) { output.textContent = error.message; }
    });
    document.getElementById('challenge-totp')?.addEventListener('click', async () => {
        try {
            const code = document.getElementById('challenge-code').value;
            const data = await jsonFetch('/api/mfa/challenge/totp', {method: 'POST', body: JSON.stringify({code})});
            location.assign(data.redirect);
        } catch (error) { document.getElementById('challenge-error').textContent = error.message; }
    });
    document.getElementById('challenge-passkey')?.addEventListener('click', async () => {
        try {
            const options = await jsonFetch('/api/mfa/passkeys/authenticate/options', {method: 'POST', body: '{}'});
            options.challenge = decode(options.challenge);
            options.allowCredentials = (options.allowCredentials || []).map(c => ({...c, id: decode(c.id)}));
            const credential = await navigator.credentials.get({publicKey: options});
            const data = await jsonFetch('/api/mfa/passkeys/authenticate/verify', {method: 'POST', body: JSON.stringify({credential: credentialJSON(credential)})});
            location.assign(data.redirect);
        } catch (error) { document.getElementById('challenge-error').textContent = error.message; }
    });
})();
