import 'package:equatable/equatable.dart';

class UserEntity extends Equatable {
  final String email;
  final String? fullName;
  final String? accessToken;

  const UserEntity({
    required this.email,
    this.fullName,
    this.accessToken,
  });

  bool get isAuthenticated =>
      accessToken != null && accessToken!.trim().isNotEmpty;

  @override
  List<Object?> get props => [email, fullName, accessToken];
}
