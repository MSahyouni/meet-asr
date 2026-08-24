import 'package:audioplayers/audioplayers.dart';

class AudioPlayerService {
  final AudioPlayer _player = AudioPlayer();

  Stream<void> get onComplete {
    return _player.onPlayerComplete.map((_) {});
  }

  Future<void> play(String path) async {
    await _player.play(
      DeviceFileSource(path),
    );
  }

  Future<void> stop() async {
    await _player.stop();
  }

  Future<void> dispose() async {
    await _player.dispose();
  }
}