import 'package:flutter/material.dart';
import 'package:nabra/core/widgets/geometric_background.dart';
import 'package:nabra/core/widgets/nabra_header.dart';

class NabraScaffold extends StatelessWidget {
  final String title;
  final String? subtitle;
  final Widget body;
  final Widget? leading;
  final List<Widget>? actions;
  final Widget? floatingActionButton;
  final Widget? drawer;
  final GlobalKey<ScaffoldState>? scaffoldKey;
  final bool showLogo;
  final double headerHeight;
  final EdgeInsetsGeometry contentPadding;
  final Widget? bottomBar;

  const NabraScaffold({
    super.key,
    required this.title,
    required this.body,
    this.subtitle,
    this.leading,
    this.actions,
    this.floatingActionButton,
    this.drawer,
    this.scaffoldKey,
    this.showLogo = true,
    this.headerHeight = 168,
    this.contentPadding = const EdgeInsets.fromLTRB(20, 20, 20, 28),
    this.bottomBar,
  });

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      key: scaffoldKey,
      drawer: drawer,
      backgroundColor: Colors.transparent,
      floatingActionButton: floatingActionButton,
      body: GeometricBackground(
        child: Column(
          children: [
            NabraHeader(
              title: title,
              subtitle: subtitle,
              leading: leading,
              actions: actions,
              showLogo: showLogo,
              height: headerHeight,
            ),
            Expanded(
              child: Padding(
                padding: contentPadding,
                child: body,
              ),
            ),
            ?bottomBar,
          ],
        ),
      ),
    );
  }
}
