import 'dart:typed_data';

/// يغلّف PCM 16-bit little-endian داخل ملف WAV قياسي.
Uint8List pcm16ToWav(
  Uint8List pcm, {
  required int sampleRate,
  int numChannels = 1,
}) {
  final byteRate = sampleRate * numChannels * 2;
  final blockAlign = numChannels * 2;
  final dataLength = pcm.length;
  final fileLength = 36 + dataLength;

  final header = ByteData(44);
  void writeString(int offset, String value) {
    for (var i = 0; i < value.length; i++) {
      header.setUint8(offset + i, value.codeUnitAt(i));
    }
  }

  writeString(0, 'RIFF');
  header.setUint32(4, fileLength, Endian.little);
  writeString(8, 'WAVE');
  writeString(12, 'fmt ');
  header.setUint32(16, 16, Endian.little); // PCM chunk size
  header.setUint16(20, 1, Endian.little); // audio format = PCM
  header.setUint16(22, numChannels, Endian.little);
  header.setUint32(24, sampleRate, Endian.little);
  header.setUint32(28, byteRate, Endian.little);
  header.setUint16(32, blockAlign, Endian.little);
  header.setUint16(34, 16, Endian.little); // bits per sample
  writeString(36, 'data');
  header.setUint32(40, dataLength, Endian.little);

  final out = BytesBuilder(copy: false)
    ..add(header.buffer.asUint8List())
    ..add(pcm);
  return out.takeBytes();
}
