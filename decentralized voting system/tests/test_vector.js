const assert = require('assert');

async function testSharedVector() {
  const secretKeyHex = '11'.repeat(32);
  const voterId = 'd04ab232742bb4ab3a1368bd4615e4e6d0224ab71a016baf8520a332c9778737';
  const proposalId = 'PROP-2026-TEST';
  const choice = 'YES';
  const weight = 1;

  const payload = {
    choice: choice,
    domain: 'openballot:ballot:v1',
    proposal_id: proposalId,
    voter_id: voterId.toLowerCase(),
    weight: weight
  };

  const canonical = JSON.stringify(payload, Object.keys(payload).sort());
  const encoder = new TextEncoder();
  const digestBuffer = await crypto.subtle.digest('SHA-256', encoder.encode(canonical));
  const digestHex = Buffer.from(digestBuffer).toString('hex');
  const expectedDigest = '3f4df2f99f892e01cfcefa9dfade481f35518d41f85e1484384e813b31a5f7a9';
  assert.strictEqual(digestHex, expectedDigest, 'SHA-256 digest mismatch');

  const pkcs8Header = new Uint8Array([
    0x30, 0x2e, 0x02, 0x01, 0x00, 0x30, 0x05, 0x06, 0x03, 0x2b, 0x65, 0x70, 0x04, 0x22, 0x04, 0x20
  ]);
  const cleanHex = secretKeyHex.trim().toLowerCase();
  const secretBytes = new Uint8Array(cleanHex.match(/.{1,2}/g).map(byte => parseInt(byte, 16)));
  const pkcs8Bytes = new Uint8Array(pkcs8Header.length + secretBytes.length);
  pkcs8Bytes.set(pkcs8Header, 0);
  pkcs8Bytes.set(secretBytes, pkcs8Header.length);

  const privateKey = await crypto.subtle.importKey(
    'pkcs8',
    pkcs8Bytes,
    { name: 'Ed25519' },
    false,
    ['sign']
  );

  const sigBuffer = await crypto.subtle.sign({ name: 'Ed25519' }, privateKey, digestBuffer);
  const signatureHex = Buffer.from(sigBuffer).toString('hex');
  const expectedSig = '905abc13a792f817dc599eeee510198f9bbc949c292396a70160cb42fa207bdfbb21581a5aea809a440c1afe6c17ecc76aee0bd2d093b999d91a2d8ea7ed0f06';
  assert.strictEqual(signatureHex, expectedSig, 'Ed25519 signature mismatch');
  console.log('Shared test vector PASSED in JavaScript (WebCrypto)');
}

testSharedVector().catch(err => {
  console.error(err);
  process.exit(1);
});
