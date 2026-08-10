import 'package:flutter/material.dart';
import 'package:nabra/controllers/auth_controller.dart';
import 'package:gap/gap.dart';
import 'package:go_router/go_router.dart';

Widget get_Drawer(BuildContext context) {
  return Drawer(
    width: 260,
    child: Container(
      decoration: const BoxDecoration(
        gradient: LinearGradient(
          begin: Alignment.topLeft,
          end: Alignment.bottomRight,
          colors: [
            Color.fromARGB(255, 11, 54, 49),
            Color.fromARGB(255, 15, 75, 61),
            Color.fromARGB(255, 23, 107, 92),
          ],
        ),
      ),
      child: ListView(
        padding: EdgeInsets.zero,
        children: [
          DrawerHeader(
            decoration: BoxDecoration(
              border: Border(bottom: BorderSide(color: Colors.white24)),
            ),
            child: Column(
              crossAxisAlignment: CrossAxisAlignment.start,
              children: [
                Row(
                  children: [
                    Image.asset(
                      'assets/images/logo_gradient.png',
                      width: 60,
                      height: 60,
                    ),
                    const SizedBox(width: 20),
                    const Expanded(
                      child: Text(
                        'نبرة',
                        overflow: TextOverflow.ellipsis,
                        style: TextStyle(color: Colors.white, fontSize: 25),
                      ),
                    ),
                  ],
                ),
                const Gap(10),
                const Center(
                  child: Text(
                    'تحويل الصوت إلى نص والنص إلى صوت',
                    textAlign: TextAlign.center,
                    style: TextStyle(color: Colors.white70),
                  ),
                ),
                const Gap(10),
              ],
            ),
          ),
          Gap(5),
          Padding(
            padding: const EdgeInsets.all(15.0),
            child: Column(
              children: [
                Row(
                  children: [
                    Gap(175),
                    Text(
                      "الوصف",
                      style: TextStyle(
                        fontSize: 20,
                        color: const Color.fromARGB(179, 190, 183, 183),
                      ),
                    ),
                  ],
                ),
                Gap(5),
                Text(
                  "تطبيق ذكي يعتمد على تقنيات الذكاء الاصطناعي لتحويل الصوت إلى نص بدقة عالية، وتحويل النص إلى صوت طبيعي. يتيح تحليل التسجيلات الصوتية وتلخيصها بسهولة لتحسين الإنتاجية وإدارة المحتوى الصوتي.",
                  style: TextStyle(fontSize: 20, color: Colors.white70),
                  textDirection: TextDirection.rtl,
                ),
                Gap(150),
                SizedBox(
                  width: double.infinity,
                  height: 40,
                  child: ElevatedButton(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.transparent,
                      shadowColor: Colors.transparent,
                      padding: EdgeInsets.zero,
                      minimumSize: const Size.fromHeight(50),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                    ),
                    onPressed: () {
                      context.push('/login');
                    },
                    child: Ink(
                      decoration: BoxDecoration(
                        gradient: const LinearGradient(
                          begin: Alignment.centerLeft,
                          end: Alignment.centerRight,
                          colors: [
                            Color.fromARGB(255, 15, 71, 64),
                            Color.fromARGB(255, 18, 91, 74),
                            Color.fromARGB(255, 26, 123, 106),
                          ],
                        ),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: const Center(
                        child: Row(
                          mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                          children: [
                            Gap(35),
                            Text(
                              'تسجيل الدخول ',
                              style: TextStyle(
                                color: Colors.white,
                                fontSize: 16,
                              ),
                            ),
                            Gap(10),
                            Icon(Icons.login, color: Colors.white),
                          ],
                        ),
                      ),
                    ),
                  ),
                ),

                const Gap(20),

                SizedBox(
                  width: double.infinity,
                  height: 40,
                  child: ElevatedButton(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.transparent,
                      shadowColor: Colors.transparent,
                      padding: EdgeInsets.zero,
                      minimumSize: const Size.fromHeight(50),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                    ),
                    onPressed: () {
                      context.push('/create_account');
                    },
                    child: Ink(
                      decoration: BoxDecoration(
                        gradient: const LinearGradient(
                          begin: Alignment.centerLeft,
                          end: Alignment.centerRight,
                          colors: [
                            Color.fromARGB(255, 15, 71, 64),
                            Color.fromARGB(255, 18, 91, 74),
                            Color.fromARGB(255, 26, 123, 106),
                          ],
                        ),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: const Center(
                        child: Row(
                          mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                          children: [
                            Gap(35),
                            Text(
                              'إنشاء حساب جديد',
                              style: TextStyle(
                                color: Colors.white,
                                fontSize: 16,
                              ),
                            ),
                            Gap(10),
                            Icon(Icons.person_add, color: Colors.white),
                          ],
                        ),
                      ),
                    ),
                  ),
                ),
                Gap(20),

                SizedBox(
                  width: double.infinity,
                  height: 40,
                  child: ElevatedButton(
                    style: ElevatedButton.styleFrom(
                      backgroundColor: Colors.transparent,
                      shadowColor: Colors.transparent,
                      padding: EdgeInsets.zero,
                      minimumSize: const Size.fromHeight(50),
                      shape: RoundedRectangleBorder(
                        borderRadius: BorderRadius.circular(12),
                      ),
                    ),
                    onPressed: () {
                      AuthController.handleLogout(
                        context: context,
                        apiUrl: "",
                        onSuccess: () {
                          context.push('/login');
                        },
                      );
                    },
                    child: Ink(
                      decoration: BoxDecoration(
                        gradient: const LinearGradient(
                          begin: Alignment.centerLeft,
                          end: Alignment.centerRight,
                          colors: [
                            Color.fromARGB(255, 15, 71, 64),
                            Color.fromARGB(255, 18, 91, 74),
                            Color.fromARGB(255, 26, 123, 106),
                          ],
                        ),
                        borderRadius: BorderRadius.circular(12),
                      ),
                      child: Center(
                        child: Row(
                          mainAxisAlignment: MainAxisAlignment.spaceEvenly,
                          children: [
                            Gap(50),
                            Text(
                              'تسجيل خروج',
                              style: TextStyle(
                                color: Colors.white,
                                fontSize: 16,
                              ),
                            ),
                            Gap(10),
                            const Icon(Icons.logout, color: Colors.white),
                          ],
                        ),
                      ),
                    ),
                  ),
                ),
              ],
            ),
          ),
        ],
      ),
    ),
  );
}
